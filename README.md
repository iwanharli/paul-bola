# bola-forecasting

Statistical forecasting for the FIFA World Cup 2026, built around an xG-based
Dixon-Coles model. Started as a prediction for the England vs Argentina
semifinal (15 Jul 2026, Atlanta) and grew into a full-tournament data pipeline
+ model with honest, held-out-validated accuracy.

## TL;DR result

- **Near-even, England a razor-thin favorite.** Final model (xG/goals blend +
  time decay): England **~52% to advance** vs Argentina ~48%. Blended with the
  betting market (most accurate on held-out data): 90-min ENG 36% / draw 31% /
  ARG 33%. Effectively a coin flip with a slight England tilt.
- This still leans away from the `notes.txt` gut-pick of a confident "Argentina
  2-1". Why: Argentina scored 17 goals from only **11.25 xG** (+5.75 — partly
  unsustainable finishing), while England created **more** total xG (11.94)
  despite fewer goals. A pure-xG model over-punished Argentina (England ~62% to
  advance); the validated xG/goals blend pulls it back to near-even.
- **We do not beat the betting market.** Held-out, the market alone (77.8%
  accuracy) beats our standalone model (67.7%). Our value-add is the xG
  *explanation* and score-distribution, not out-predicting the market.

## Architecture

```
collector/   # data collection (Python + psycopg2), one script per source
  db.py                    # Postgres connection + idempotent upsert helpers
  orchestrate.py           # cron/PM2 entrypoint: auto-discovers & runs collectors
  *_collect.py             # per-source collectors (see Data sources)
  build_player_crosswalk.py# links player identities across FIFA/ESPN/ASA
db/schema.sql              # full Postgres schema (db_boforecasting)
model/
  xg_model.py              # coordinate-based xG (logistic on distance+angle)
  dixon_coles.py           # original goals-based DC model + in-sample backtest
  compare_models.py        # held-out: goals vs xG vs xG+time-decay
  compare_with_market.py   # held-out: model vs market vs blend
  validate_xg_pooling.py   # held-out: does pooling StatsBomb shots help?
  final_predict.py         # the deployable prediction (xG + market blend)
  scorer_model.py          # anytime-goalscorer probabilities per player
ecosystem.config.js        # PM2 config for scheduled collection (deploy)
```

## Data sources (all free, no paid keys)

| Source | What | Reliability |
|---|---|---|
| **openfootball/worldcup.json** | fixtures, scores, goal scorers (104 matches) | **Ground truth** for goal counts (matched official scores on all checked matches) |
| **FIFA public API** (`api.fifa.com`) | shot events w/ coordinates, squads (1241 players), referees, ~102 matches | Coordinates good; **shot/goal COUNT unreliable** (drops some goals & differs from ESPN) — use for LOCATION only |
| **ESPN public API** (`site.api.espn.com`) | starting XI, possession/shots/cards, structured odds (~102 matches) | Reliable; **preferred for shot volume & odds** |
| **Understat** | club xG per match, 6 leagues 2025/26 (1991 matches) | Reliable club-form base rates (EPL/La Liga/Bundesliga/Serie A/Ligue 1/RFPL) |
| **American Soccer Analysis** (`app.americansocceranalysis.com`) | MLS player xG, per-game + season (Messi/De Paul) | Reliable; fills MLS gap Understat lacks |
| **StatsBomb open data** (`statsbombpy`) | 3624 historical shots (WC2022/Euro2024/Copa2024) w/ real xG | Used to enlarge xG training set + validate our xG |
| **eloratings.net** | national-team Elo (16 teams) | Opponent-strength prior |
| **Open-Meteo** | weather at kickoff (13 matches) | Reliable; **collected but not yet used in model** |

### Sources tried and rejected
- **TheStatsAPI** — API key had no active subscription (403 KEY_REVOKED).
- **Sofascore / ScraperFC** — needs browser automation (botasaurus) that fails
  headless + Cloudflare-blocked. **Not needed** — ESPN covered the same data.
- **FBref** — 403 on scrape; also lost its Opta xG licence Jan 2026 (stale).

## The model

**Dixon-Coles on xG** (not raw goals), fit on all 101 finished matches:
- Each team gets attack/defense strength via max-likelihood on team xG.
- xG computed by our own logistic model: `P(goal) ~ distance + angle` to goal,
  trained on 6369 pooled shots (2745 FIFA WC2026 + 3624 StatsBomb), then
  rescaled so total xG matches WC2026's actual goal count.
- Exponential **time decay** (20-day half-life) weights recent form more.
- Thin-sample teams' strength **shrunk toward an Elo-derived prior**.
- `rho` (low-score correlation) **fixed at -0.13** (Dixon-Coles 1997 value) —
  our data couldn't identify it (MLE hit every bound we set).
- Final deployable number **blends 25% model / 75% market**.

### Held-out validation (train on group stage, test on 31 knockout matches)

| Model | Result accuracy | Log-loss |
|---|---|---|
| Raw goals (original) | 61.3% | 0.902 |
| **xG-based** | **67.7%** | 0.883 |
| xG + time decay | 67.7% | 0.881 |
| xG + pooled StatsBomb | 67.7% | 0.876 |
| **xG/goals 50/50 blend** | **71.0%** | **0.831** |
| **Market alone** | **77.8%** | **0.720** |
| **Blend 25% model / 75% market** | **81.5%** | 0.749 |

xG beats raw goals by a real ~6 points. A **xG/goals blend** then beats pure xG
(0.831 vs 0.878 log-loss) — pure xG over-regresses finishing (addresses
limitation #7). The market is still the strongest single signal.

### Anytime goalscorer model (`scorer_model.py`)

Splits each team's predicted match goals into **open-play** (distributed by
players' open-play xG share) and **penalty** (assigned entirely to the
designated taker), then `P(scores) = 1 - exp(-player_expected_goals)`. Drops
injured/suspended players (`player_availability`). Penalty-aware top picks:

| Argentina | P(scores) | England | P(scores) |
|---|---|---|---|
| Messi (pen taker) | 53.4% | Bellingham | 47.5% |
| Mac Allister | 24.2% | Kane (pen taker) | 43.7% |
| Lautaro Martínez | 20.0% | O'Reilly | 22.9% |

(Uses the same xG/goals blend as the match model, so Argentina's higher
expected goals lift their scorers — Messi is the top pick overall.) Penalty
handling: designated takers Kane (ENG) / Messi (ARG). **Messi gains** the
penalty mass (assigned duty); **Kane unchanged** (already the tournament's
actual taker, so his 2 pens were always in his numbers). Honest note: the
6-match sample shows Lautaro, not Messi, took Argentina's only pen — "Messi
takes pens" is a real-world prior overriding the small sample. Caveats:
tournament-xG based (6 matches), penalty rate high-variance, role assumed
constant.

## Known limitations & shortcomings (honest)

1. **We can't beat the market.** With only free public data, the model's best
   role is as a secondary signal + explanation, not a market-beater.
2. **Small samples.** 31 held-out matches means sub-1-point accuracy
   differences are noise. 6 knockout matches per team makes team strength
   noisy (partly mitigated by Elo shrinkage + xG).
3. **Our xG model is coarse.** Only distance + angle (Brier 0.094 vs
   StatsBomb's full-feature 0.075). No shot type, body part, defender
   positions (FIFA data doesn't expose them).
4. **Collected-but-unused signals.** Weather, lineups, injuries, referee
   tendency are in the DB but **not wired into the rate model**. So e.g.
   Henderson's absence and Atlanta's heat don't affect the number yet.
5. **Cross-source player IDs are name-matched**, not shared IDs (FIFA/ESPN/ASA
   use different namespaces). 96% match rate; accented/variant names can slip.
6. ~~Knockout ET/penalty resolution is crude.~~ **IMPROVED** — ET now uses a
   fatigue/caution-discounted rate (30/90 × 0.80, not a flat ⅓) so more ties
   reach the shootout (~41% of the draw slice), with named/configurable
   constants and a transparent ET-vs-shootout breakdown. Shootout stays 50/50
   (no shootout data in the DB); Argentina's Emiliano Martínez is a real but
   deliberately-unmodeled edge (`SHOOTOUT_ARG_WIN` is configurable). Still only
   affects the ~20% draw slice, so impact on the headline number is small.
7. ~~Elite finishers may defy xG regression.~~ **ADDRESSED** — the model now
   uses a held-out-validated 50/50 xG/goals blend instead of pure xG, which
   over-regressed finishing. This tempered the England lean into a near-even
   call (see `compare_blend.py`). Residual: the exact blend weight is uncertain
   on 31 matches (best log-loss at 0.25, best accuracy at ~0.7; 0.5 is a
   principled middle).
8. **`player_availability`/`referee_tendency` are tiny/manual** (weak priors,
   small n) — inherent, no free structured source. The empty `players`/
   `player_match_stats` legacy tables were **dropped** (superseded by
   `fifa_squads` + `player_crosswalk` and `fifa_shot_events` +
   `asa_player_game_xg`).

## Running it

```bash
# collectors (need collector/.env with Postgres creds; venv with requirements.txt)
cd collector
../venv/bin/python orchestrate.py          # DYNAMIC refresh (cron/PM2 default)
../venv/bin/python orchestrate.py --full   # also re-pull static club sources

# model
cd ../model
../venv/bin/python final_predict.py        # the deployable prediction
../venv/bin/python scorer_model.py         # anytime-goalscorer probabilities
../venv/bin/python compare_with_market.py  # held-out model-vs-market evidence
```

**Automated collection (PM2, `ecosystem.config.js`, 15-min cron).** The
orchestrator auto-discovers matches in a rolling window and refreshes, tournament-wide:
worldcup scores, Elo, ESPN roster/stats/odds, FIFA shots/squads/officials,
weather, and the player crosswalk — all idempotent (upsert), verified end-to-end.

**Not auto-refetched by design** (documented in `orchestrate.py` / `ecosystem.config.js`):
- *Static* — `statsbomb_shots` (historical), Understat/ASA club seasons (2025/26
  complete). Seed once; `--full` or `REFRESH_CLUB=1` forces a re-pull.
- *Manual* — `h2h_history`, `match_odds_snapshot`, `player_availability`,
  `referee_tendency` (no free structured source; curated by hand).

First-time DB seed steps are listed at the top of `ecosystem.config.js`.

## Database

Postgres `db_boforecasting`. Current row counts: worldcup_matches 104,
fifa_shot_events 2760, statsbomb_shots 3624, fifa_squads 1241,
player_crosswalk 1241, understat_matches 1991, espn_match_rosters 5169,
espn_match_team_stats 204, espn_match_odds 159, asa_player_season_xg 718,
team_elo_ratings 16, match_weather 13. See `db/schema.sql` for the full schema
with per-table provenance comments.
# paul-bola
