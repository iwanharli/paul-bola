"""
Honest, out-of-sample comparison of Dixon-Coles variants, to decide which
changes actually improve accuracy rather than just looking sophisticated.

Split: train on GROUP STAGE only, test on KNOCKOUT matches. Every knockout
team played the group stage, so their strengths are estimable; and no test
match is seen during fitting, so held-out log-loss is a genuine predictive
metric (unlike the earlier in-sample backtest).

Variants compared:
  A. goals   -- Dixon-Coles on full-time goals (the original model)
  B. xg      -- Dixon-Coles on our computed team xG instead of goals
  C. xg+decay-- xG + exponential time-decay weighting (recent matches count more)

We keep whichever variant wins on held-out log-loss + result accuracy.
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
KNOCKOUT_START = pd.Timestamp("2026-06-28")  # R16 begins; group stage is strictly before


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


def neg_log_lik(params, obs, team_idx, n_teams, weights, use_continuous):
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    ll = 0.0
    for (i, j, v1, v2), w in zip(obs, weights):
        lam = np.exp(attack[i] - defense[j])
        mu = np.exp(attack[j] - defense[i])
        if use_continuous:
            # xG is continuous -> use Poisson density on a non-integer "rate
            # matched to observed xG" via the Poisson log-likelihood treating
            # xG as the observed count (standard trick for xG-based DC).
            ll += w * (v1 * np.log(lam) - lam + v2 * np.log(mu) - mu)
        else:
            g1, g2 = int(v1), int(v2)
            p = poisson.pmf(g1, lam) * poisson.pmf(g2, mu) * tau(g1, g2, lam, mu, rho=FIXED_RHO)
            ll += w * np.log(max(p, 1e-10))
    return -ll


def fit(train_df, team_idx, n_teams, value_cols, weights):
    obs = [(team_idx[r.team1], team_idx[r.team2], getattr(r, value_cols[0]), getattr(r, value_cols[1]))
           for r in train_df.itertuples()]
    use_continuous = value_cols[0] == "xg1"
    x0 = np.zeros(2 * n_teams)
    res = minimize(neg_log_lik, x0, args=(obs, team_idx, n_teams, weights, use_continuous),
                   method="L-BFGS-B", bounds=[(-3, 3)] * (2 * n_teams))
    attack = res.x[:n_teams] - res.x[:n_teams].mean()
    defense = res.x[n_teams:2 * n_teams]
    return attack, defense


def shrink(attack, defense, teams, counts, elo_map):
    elo = np.array([elo_map.get(t, 1500) for t in teams])
    z = (elo - elo.mean()) / elo.std()
    pa, pd_ = z * 0.3, -z * 0.3
    for i, t in enumerate(teams):
        n = counts.get(t, 0)
        w = n / (n + ELO_PRIOR_WEIGHT)
        attack[i] = w * attack[i] + (1 - w) * pa[i]
        defense[i] = w * defense[i] + (1 - w) * pd_[i]
    return attack, defense


def predict_result_probs(attack, defense, team_idx, ta, tb, rho=FIXED_RHO, max_g=8):
    i, j = team_idx[ta], team_idx[tb]
    lam = np.exp(attack[i] - defense[j])
    mu = np.exp(attack[j] - defense[i])
    ph = pdw = pa = 0.0
    for x in range(max_g + 1):
        for y in range(max_g + 1):
            p = poisson.pmf(x, lam) * poisson.pmf(y, mu) * tau(x, y, lam, mu, rho)
            if x > y:
                ph += p
            elif x == y:
                pdw += p
            else:
                pa += p
    s = ph + pdw + pa
    return ph / s, pdw / s, pa / s


def evaluate(df, value_cols, use_decay, elo_map, label):
    train = df[df["date"] < KNOCKOUT_START].copy()
    test = df[df["date"] >= KNOCKOUT_START].copy()

    teams = sorted(set(train["team1"]) | set(train["team2"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)

    counts = {}
    for r in train.itertuples():
        counts[r.team1] = counts.get(r.team1, 0) + 1
        counts[r.team2] = counts.get(r.team2, 0) + 1

    if use_decay:
        latest = train["date"].max()
        half_life_days = 20.0
        weights = np.array([0.5 ** ((latest - d).days / half_life_days) for d in train["date"]])
    else:
        weights = np.ones(len(train))

    attack, defense = fit(train, team_idx, n_teams, value_cols, weights)
    attack, defense = shrink(attack, defense, teams, counts, elo_map)

    log_loss, correct, n_eval = 0.0, 0, 0
    for r in test.itertuples():
        if r.team1 not in team_idx or r.team2 not in team_idx:
            continue  # a knockout team that didn't appear in group-stage train set
        ph, pdw, pa = predict_result_probs(attack, defense, team_idx, r.team1, r.team2)
        actual = "h" if r.g1 > r.g2 else ("d" if r.g1 == r.g2 else "a")
        actual_p = {"h": ph, "d": pdw, "a": pa}[actual]
        log_loss += -np.log(max(actual_p, 1e-10))
        pred = max([("h", ph), ("d", pdw), ("a", pa)], key=lambda t: t[1])[0]
        if pred == actual:
            correct += 1
        n_eval += 1

    print(f"{label:14s} | held-out matches={n_eval:2d} | "
          f"result acc={correct}/{n_eval}={correct/n_eval:.1%} | "
          f"avg log-loss={log_loss/n_eval:.3f}")
    return log_loss / n_eval, correct / n_eval


def main():
    conn = db.connect()
    try:
        xg_df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
    finally:
        conn.close()
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    print(f"\nGroup-stage train / knockout test split (knockout from {KNOCKOUT_START.date()})")
    print("=" * 70)
    evaluate(xg_df, ("g1", "g2"), False, elo_map, "A. goals")
    evaluate(xg_df, ("xg1", "xg2"), False, elo_map, "B. xg")
    evaluate(xg_df, ("xg1", "xg2"), True, elo_map, "C. xg+decay")
    print("=" * 70)
    print("Lower log-loss = better calibrated. Result acc is coarser (W/D/L only).")


if __name__ == "__main__":
    main()
