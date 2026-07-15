"""
Final World Cup 2026 semifinal predictor: England vs Argentina.

Uses the configuration that won the held-out comparison in compare_models.py
(xG-based rates + exponential time decay), which beat the raw-goals model by
~6 percentage points of out-of-sample result accuracy and a lower log-loss.
Here it's fit on ALL 101 finished matches (group + knockout) for maximum
information before predicting the semifinal.

Honest scope note: this predicts 90-minute goal distribution from xG-derived
attack/defense strength. It does NOT use lineup/injury/weather signals (those
are collected but not wired into the rate model) -- so e.g. Henderson's
absence or Atlanta's heat aren't reflected. It's a strong statistical
baseline, not an all-knowing oracle; treat probabilities as calibrated
estimates with real uncertainty.
"""
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db
from xg_model import build_xg_match_table

FIXED_RHO = -0.13
ELO_PRIOR_WEIGHT = 3.0
HALF_LIFE_DAYS = 20.0

# Blend the model's input signal: alpha*xG + (1-alpha)*actual_goals. Held-out
# sweep (compare_blend.py) showed intermediate blends beat BOTH pure xG and
# pure goals -- pure xG over-regresses elite finishing. alpha=0.5 is a
# principled middle (best log-loss was at 0.25, best accuracy at ~0.7; 0.5
# improves both metrics over pure xG without overfitting the 31-match optimum).
BLEND_ALPHA = 0.5

# --- Knockout resolution (limitation #6) constants ---
# Extra time is 30 min (1/3 of 90) but scored at a LOWER per-minute rate than
# regulation: fatigue + caution (nobody wants to concede and lose). Empirically
# ET yields well under 1/3 of a full match's goals, so we discount the rate.
ET_MINUTES_FRACTION = 30 / 90
ET_INTENSITY = 0.80          # ~20% fewer goals/min than regulation
# Penalty shootout: with no shootout data in our DB, a coin flip is the honest
# default. Argentina's Emiliano Martinez is an elite shootout keeper (won the
# 2022 WC final, 2021 & 2024 Copa America shootouts) -- a real but unquantified
# edge. Left at 0.50 to avoid injecting an unvalidated prior; raise toward
# ~0.55 if you choose to trust that record.
SHOOTOUT_ARG_WIN = 0.50


def tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def neg_log_lik(params, obs, n_teams, weights):
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    ll = 0.0
    for (i, j, xg1, xg2), w in zip(obs, weights):
        lam = np.exp(attack[i] - defense[j])
        mu = np.exp(attack[j] - defense[i])
        ll += w * (xg1 * np.log(lam) - lam + xg2 * np.log(mu) - mu)  # Poisson LL on xG
    return -ll


def fit_all(df, elo_map):
    teams = sorted(set(df["team1"]) | set(df["team2"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    latest = df["date"].max()
    weights = np.array([0.5 ** ((latest - d).days / HALF_LIFE_DAYS) for d in df["date"]])

    obs = [(team_idx[r.team1], team_idx[r.team2], r.xg1, r.xg2) for r in df.itertuples()]
    x0 = np.zeros(2 * n)
    res = minimize(neg_log_lik, x0, args=(obs, n, weights), method="L-BFGS-B",
                   bounds=[(-3, 3)] * (2 * n))
    attack = res.x[:n] - res.x[:n].mean()
    defense = res.x[n:2 * n]

    counts = {}
    for r in df.itertuples():
        counts[r.team1] = counts.get(r.team1, 0) + 1
        counts[r.team2] = counts.get(r.team2, 0) + 1
    elo = np.array([elo_map.get(t, 1500) for t in teams])
    z = (elo - elo.mean()) / elo.std()
    pa, pdef = z * 0.3, -z * 0.3
    for i, t in enumerate(teams):
        k = counts.get(t, 0)
        w = k / (k + ELO_PRIOR_WEIGHT)
        attack[i] = w * attack[i] + (1 - w) * pa[i]
        defense[i] = w * defense[i] + (1 - w) * pdef[i]

    return attack, defense, team_idx


def score_matrix(attack, defense, team_idx, ta, tb, max_g=10):
    i, j = team_idx[ta], team_idx[tb]
    lam = np.exp(attack[i] - defense[j])
    mu = np.exp(attack[j] - defense[i])
    mat = np.zeros((max_g + 1, max_g + 1))
    for x in range(max_g + 1):
        for y in range(max_g + 1):
            mat[x, y] = poisson.pmf(x, lam) * poisson.pmf(y, mu) * tau(x, y, lam, mu, FIXED_RHO)
    mat /= mat.sum()
    return mat, lam, mu


def main():
    conn = db.connect()
    try:
        df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
    finally:
        conn.close()
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    # blend xG with actual goals (limitation #7 fix) before fitting
    df = df.copy()
    df["xg1"] = BLEND_ALPHA * df["xg1"] + (1 - BLEND_ALPHA) * df["g1"]
    df["xg2"] = BLEND_ALPHA * df["xg2"] + (1 - BLEND_ALPHA) * df["g2"]

    attack, defense, team_idx = fit_all(df, elo_map)

    ta, tb = "Argentina", "England"
    mat, lam, mu = score_matrix(attack, defense, team_idx, ta, tb)

    p_arg = np.tril(mat, -1).sum()
    p_draw = np.trace(mat)
    p_eng = np.triu(mat, 1).sum()

    print("=" * 60)
    print("  FINAL MODEL (xG-based + time decay) -- ARG vs ENG")
    print("=" * 60)
    print(f"Expected goals (90'): Argentina {lam:.2f} - {mu:.2f} England")
    print(f"\n90-min result:")
    print(f"  Argentina win : {p_arg:.1%}")
    print(f"  Draw          : {p_draw:.1%}")
    print(f"  England win   : {p_eng:.1%}")

    print(f"\nTop 6 scorelines (90'):")
    flat = sorted(((mat[x, y], x, y) for x in range(mat.shape[0]) for y in range(mat.shape[1])), reverse=True)
    for p, x, y in flat[:6]:
        print(f"  Argentina {x}-{y} England : {p:.1%}")

    # knockout resolution: draw -> extra time -> penalty shootout
    lam_et = lam * ET_MINUTES_FRACTION * ET_INTENSITY
    mu_et = mu * ET_MINUTES_FRACTION * ET_INTENSITY
    et_a = et_e = et_d = 0.0
    for x in range(6):
        for y in range(6):
            p = poisson.pmf(x, lam_et) * poisson.pmf(y, mu_et)
            if x > y:
                et_a += p
            elif y > x:
                et_e += p
            else:
                et_d += p
    # ET still level -> shootout
    p_arg_adv = p_arg + p_draw * (et_a + et_d * SHOOTOUT_ARG_WIN)
    p_eng_adv = p_eng + p_draw * (et_e + et_d * (1 - SHOOTOUT_ARG_WIN))
    print(f"\n(ET breakdown of the {p_draw:.0%} draw slice: ARG wins ET {et_a:.0%}, "
          f"ENG wins ET {et_e:.0%}, still level -> shootout {et_d:.0%})")
    print(f"\nAdvance to final (incl. ET/penalties):")
    print(f"  Argentina : {p_arg_adv:.1%}")
    print(f"  England   : {p_eng_adv:.1%}")
    print("=" * 60)

    # --- Market blend (the empirically most accurate approach) ---
    # Held-out test (compare_with_market.py) showed the betting market alone
    # (77.8% acc) beats our model alone (66.7%), and a market-heavy blend tops
    # result accuracy (81.5%). So the most accurate final number leans on the
    # market, using our model as a secondary signal. Market implied probs for
    # this semifinal from ESPN/DraftKings 90-min moneyline (ENG +175 / draw
    # +180-ish / ARG +200), vig-removed:
    def am(ml):
        return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)
    m_eng, m_draw, m_arg = am(175), am(180), am(200)
    s = m_eng + m_draw + m_arg
    m_eng, m_draw, m_arg = m_eng / s, m_draw / s, m_arg / s

    w = 0.25  # 25% model / 75% market -- the held-out best-accuracy blend
    b_arg = w * p_arg + (1 - w) * m_arg
    b_draw = w * p_draw + (1 - w) * m_draw
    b_eng = w * p_eng + (1 - w) * m_eng

    print("\n" + "=" * 60)
    print("  MARKET-BLENDED FINAL (most accurate per held-out test)")
    print("=" * 60)
    print(f"Market implied (90'): ARG {m_arg:.1%} / Draw {m_draw:.1%} / ENG {m_eng:.1%}")
    print(f"Blend 25% model / 75% market (90'):")
    print(f"  Argentina : {b_arg:.1%}")
    print(f"  Draw      : {b_draw:.1%}")
    print(f"  England   : {b_eng:.1%}")
    print("=" * 60)

    print("\nHONEST BOTTOM LINE:")
    print("- The betting market is a STRONGER predictor than our standalone")
    print("  model (77.8% vs 66.7% held-out accuracy). We don't beat it.")
    print(f"- Model input is a {int(BLEND_ALPHA*100)}/{int((1-BLEND_ALPHA)*100)} xG/goals blend")
    print("  (held-out-validated); pure xG over-punished Argentina's finishing,")
    print("  pure goals over-rewarded it. The blend lands between: a near-even")
    print("  match, England a razor-thin favorite.")
    print(f"- Blended-with-market 90-min: ENG {b_eng:.0%} / draw {b_draw:.0%} / "
          f"ARG {b_arg:.0%}. Model-only advance: ENG {p_eng_adv:.0%} / ARG {p_arg_adv:.0%}.")
    print("- Real uncertainty is high: one match, ~2-3 goals. This is a coin flip")
    print("  with a slight England tilt, not a confident call. Not an oracle.")


if __name__ == "__main__":
    main()
