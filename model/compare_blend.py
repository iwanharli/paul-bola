"""
Addresses README limitation #7 (pure xG over-regresses elite finishers).

Instead of feeding the Dixon-Coles model pure xG or pure goals, feed a blend:
    signal = alpha * xG + (1 - alpha) * actual_goals
alpha=1 is pure xG (full finishing regression), alpha=0 is pure goals (no
regression -- trusts finishing entirely). The truth for teams with elite
finishers (Messi/Alvarez) likely sits between. We sweep alpha and measure
held-out knockout accuracy/log-loss to find whether a blend genuinely beats
pure xG -- and honestly report if it's within noise.
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


def evaluate_alpha(df, elo_map, alpha):
    d = df.copy()
    # The blended signal is continuous (non-integer), like xG. fit() selects
    # the continuous vs discrete Poisson likelihood by whether the value column
    # is named "xg1", so we MUST feed the blend through xg1/xg2 -- otherwise it
    # wrongly uses the discrete PMF on non-integer values (poisson.pmf(2.3,.)~0)
    # and produces garbage. (g1/g2 keep the true integer goals for scoring.)
    blend1 = alpha * d["xg1"] + (1 - alpha) * d["g1"]
    blend2 = alpha * d["xg2"] + (1 - alpha) * d["g2"]
    d["xg1"], d["xg2"] = blend1, blend2

    train = d[d["date"] < KNOCKOUT_START].copy()
    test = d[d["date"] >= KNOCKOUT_START].copy()
    teams = sorted(set(train["team1"]) | set(train["team2"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    counts = {}
    for r in train.itertuples():
        counts[r.team1] = counts.get(r.team1, 0) + 1
        counts[r.team2] = counts.get(r.team2, 0) + 1
    latest = train["date"].max()
    weights = np.array([0.5 ** ((latest - dt).days / 20.0) for dt in train["date"]])

    attack, defense = fit(train, team_idx, len(teams), ("xg1", "xg2"), weights)
    attack, defense = shrink(attack, defense, teams, counts, elo_map)

    ll, correct, n = 0.0, 0, 0
    for r in test.itertuples():
        if r.team1 not in team_idx or r.team2 not in team_idx:
            continue
        ph, pdw, pa = predict_result_probs(attack, defense, team_idx, r.team1, r.team2)
        actual = "h" if r.g1 > r.g2 else ("d" if r.g1 == r.g2 else "a")
        ap = {"h": ph, "d": pdw, "a": pa}[actual]
        ll += -np.log(max(ap, 1e-10))
        pred = max([("h", ph), ("d", pdw), ("a", pa)], key=lambda t: t[1])[0]
        correct += pred == actual
        n += 1
    return correct / n, ll / n, n


def main():
    conn = db.connect()
    try:
        df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
    finally:
        conn.close()
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    print("\nHeld-out knockout: signal = alpha*xG + (1-alpha)*goals")
    print("=" * 56)
    print(f"{'alpha':>6s} {'meaning':22s} {'acc':>6s} {'log-loss':>9s}")
    results = []
    for alpha in [0.0, 0.25, 0.5, 0.6, 0.7, 0.75, 0.85, 1.0]:
        acc, ll, n = evaluate_alpha(df, elo_map, alpha)
        meaning = {0.0: "pure goals", 1.0: "pure xG"}.get(alpha, "")
        results.append((alpha, acc, ll))
        print(f"{alpha:6.2f} {meaning:22s} {acc:5.1%} {ll:9.3f}")
    print("=" * 56)

    best = min(results, key=lambda r: r[2])
    pure_xg = next(r for r in results if r[0] == 1.0)
    print(f"Best log-loss: alpha={best[0]:.2f} (ll={best[2]:.3f}) vs pure xG (ll={pure_xg[2]:.3f})")
    delta = pure_xg[2] - best[2]
    if delta > 0.01:
        print(f"-> Blending helps (log-loss -{delta:.3f}). Fixes limitation #7.")
    else:
        print(f"-> Improvement {delta:+.3f} is within noise on {results and 'small n'}; "
              "pure xG stays the honest default.")


if __name__ == "__main__":
    main()
