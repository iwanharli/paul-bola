"""
Does pooling StatsBomb shots into the xG model actually improve out-of-sample
accuracy? Two checks:

  1. Calibration of OUR coordinate-based xG vs StatsBomb's proprietary xG on
     the same StatsBomb shots (are our numbers trustworthy at all?).
  2. Held-out knockout accuracy of the full pipeline with the xG model trained
     on FIFA-only vs FIFA+StatsBomb -- the only thing that proves the enlarged
     training set helps the actual prediction task, not just looks nicer.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db
from xg_model import build_xg_match_table, fit_xg_model, statsbomb_features
from compare_models import fit, shrink, predict_result_probs, KNOCKOUT_START


def calibration_vs_statsbomb(conn):
    sb = pd.read_sql("""
        SELECT location_x AS x, location_y AS y, is_goal, statsbomb_xg
        FROM statsbomb_shots
        WHERE statsbomb_xg IS NOT NULL AND location_x IS NOT NULL
    """, conn)
    model = fit_xg_model(conn, pool_statsbomb=True)
    feats = np.array([statsbomb_features(r.x, r.y) for r in sb.itertuples()])
    our_xg = model.predict_proba(feats)[:, 1]

    actual = sb["is_goal"].astype(int).values
    print("\n=== Calibration on StatsBomb shots ===")
    print(f"  Actual goals            : {actual.sum()}")
    print(f"  Our model total xG      : {our_xg.sum():.1f}")
    print(f"  StatsBomb total xG      : {sb['statsbomb_xg'].sum():.1f}")
    print(f"  Corr(our xG, SB xG)     : {np.corrcoef(our_xg, sb['statsbomb_xg'])[0,1]:.3f}")
    print(f"  Our model Brier         : {np.mean((our_xg - actual)**2):.4f}")
    print(f"  StatsBomb Brier         : {np.mean((sb['statsbomb_xg'] - actual)**2):.4f}")
    print("  (Brier lower=better; ours is a 2-feature model vs their full one)")


def heldout_accuracy(conn, pool):
    df, _ = build_xg_match_table(conn, pool_statsbomb=pool)
    elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    train = df[df["date"] < KNOCKOUT_START].copy()
    test = df[df["date"] >= KNOCKOUT_START].copy()
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
        calibration_vs_statsbomb(conn)
        print("\n=== Held-out knockout accuracy: FIFA-only vs FIFA+StatsBomb xG model ===")
        acc0, ll0, n = heldout_accuracy(conn, pool=False)
        acc1, ll1, _ = heldout_accuracy(conn, pool=True)
        print(f"  FIFA-only     | acc={acc0:.1%} | log-loss={ll0:.3f}")
        print(f"  FIFA+StatsBomb| acc={acc1:.1%} | log-loss={ll1:.3f}")
        print(f"  ({n} held-out matches)")
        verdict = "HELPS" if ll1 < ll0 else "does NOT help (or noise)"
        print(f"  Verdict on log-loss: pooling {verdict}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
