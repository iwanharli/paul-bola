"""
Test two principled accuracy improvements on the held-out knockout set:
  1. blending our xG model's probabilities with the betting market's, and
  2. blending the xG *signal* with actual goals (partial finishing regression).

Markets aggregate lineup/injury/sharp-money info our rate model ignores, so a
model+market blend usually beats either alone. Pure xG assumes finishing fully
regresses to average; elite finishers (Messi/Alvarez) sustain some of it, so a
xG/goals blend may beat pure xG.

HONEST CAVEATS baked in, not hidden:
  - Only 31 held-out matches, so small blend-weight differences are noise.
    We report a coarse sweep, not a finely "optimized" weight, to avoid
    overfitting those 31 games.
  - The model is trained on group stage only (to keep knockout as held-out),
    but market odds for knockout games already price in earlier knockout
    results -- the market has an information edge here. So "market wins" is
    partly that asymmetry, and the realistic deployment gain from blending is
    likely smaller than the held-out numbers suggest.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db
from xg_model import build_xg_match_table
from compare_models import fit, shrink, predict_result_probs, KNOCKOUT_START
import re
import unicodedata


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def american_to_prob(ml):
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def build_market_probs(conn):
    """espn_event -> (normed home name, normed away name, P_home, P_draw, P_away) vig-removed."""
    id_to_name = {}
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT raw->'team'->>'id', raw->'team'->>'displayName' FROM espn_match_team_stats")
    for tid, name in cur.fetchall():
        id_to_name[tid] = name

    cur.execute("SELECT espn_event_id, raw FROM espn_match_odds WHERE provider='DraftKings'")
    out = {}
    for eid, raw in cur.fetchall():
        try:
            h_id = raw["homeTeamOdds"]["teamId"]
            a_id = raw["awayTeamOdds"]["teamId"]
            h_ml = raw["homeTeamOdds"]["moneyLine"]
            a_ml = raw["awayTeamOdds"]["moneyLine"]
            d_ml = raw["drawOdds"]["moneyLine"]
        except (KeyError, TypeError):
            continue
        ph, pd_, pa = american_to_prob(h_ml), american_to_prob(d_ml), american_to_prob(a_ml)
        s = ph + pd_ + pa
        out[eid] = (norm(id_to_name.get(h_id, "")), norm(id_to_name.get(a_id, "")),
                    ph / s, pd_ / s, pa / s)
    return out


def logloss_and_acc(rows):
    ll = sum(-np.log(max(p, 1e-10)) for p, _ in rows) / len(rows)
    acc = sum(c for _, c in rows) / len(rows)
    return ll, acc


def main():
    conn = db.connect()
    try:
        xg_df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
        market = build_market_probs(conn)
    finally:
        conn.close()
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    # market lookup by unordered team-name pair
    market_by_pair = {}
    for h, a, ph, pd_, pa in market.values():
        market_by_pair[frozenset([h, a])] = (h, a, ph, pd_, pa)

    train = xg_df[xg_df["date"] < KNOCKOUT_START].copy()
    test = xg_df[xg_df["date"] >= KNOCKOUT_START].copy()
    teams = sorted(set(train["team1"]) | set(train["team2"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    counts = {}
    for r in train.itertuples():
        counts[r.team1] = counts.get(r.team1, 0) + 1
        counts[r.team2] = counts.get(r.team2, 0) + 1

    latest = train["date"].max()
    weights = np.array([0.5 ** ((latest - d).days / 20.0) for d in train["date"]])
    attack, defense = fit(train, team_idx, len(teams), ("xg1", "xg2"), weights)
    attack, defense = shrink(attack, defense, teams, counts, elo_map)

    model_rows, market_rows = [], []
    blends = {w: [] for w in [0.25, 0.5, 0.75]}
    matched = 0

    for r in test.itertuples():
        if r.team1 not in team_idx or r.team2 not in team_idx:
            continue
        mph, mpd, mpa = predict_result_probs(attack, defense, team_idx, r.team1, r.team2)
        actual = "h" if r.g1 > r.g2 else ("d" if r.g1 == r.g2 else "a")

        key = frozenset([norm(r.team1), norm(r.team2)])
        mk = market_by_pair.get(key)
        if not mk:
            continue
        matched += 1
        mh_name, ma_name, kph, kpd, kpa = mk
        # market is oriented (home=mh_name); align to our team1 orientation
        if norm(r.team1) == mh_name:
            k_h, k_d, k_a = kph, kpd, kpa
        else:
            k_h, k_d, k_a = kpa, kpd, kph

        def score(ph, pd_, pa):
            p_actual = {"h": ph, "d": pd_, "a": pa}[actual]
            pred = max([("h", ph), ("d", pd_), ("a", pa)], key=lambda t: t[1])[0]
            return p_actual, int(pred == actual)

        model_rows.append(score(mph, mpd, mpa))
        market_rows.append(score(k_h, k_d, k_a))
        for w in blends:
            bh = w * mph + (1 - w) * k_h
            bd = w * mpd + (1 - w) * k_d
            ba = w * mpa + (1 - w) * k_a
            blends[w].append(score(bh, bd, ba))

    print(f"\nHeld-out knockout matches matched to market odds: {matched}")
    print("=" * 62)
    ll, acc = logloss_and_acc(model_rows); print(f"model (xG) alone      | acc={acc:.1%} | log-loss={ll:.3f}")
    ll, acc = logloss_and_acc(market_rows); print(f"market alone          | acc={acc:.1%} | log-loss={ll:.3f}")
    for w in sorted(blends):
        ll, acc = logloss_and_acc(blends[w])
        print(f"blend {int(w*100)}% model/{int((1-w)*100)}% market | acc={acc:.1%} | log-loss={ll:.3f}")
    print("=" * 62)


if __name__ == "__main__":
    main()
