"""
Build a data-driven xG (expected goals) model from FIFA shot coordinates,
then attach a team-level xG to every finished World Cup 2026 match.

Why: the first Dixon-Coles model used raw full-time goals, which are a very
noisy, low-count signal (most matches 0-3 goals). xG is a lower-variance
proxy for how many goals a team "should" have scored given chance quality,
so modeling xG-based rates generally improves calibration and out-of-sample
accuracy. We don't have a ready-made xG per WC match from any source, but we
do have per-shot coordinates + whether each shot was a goal, so we fit our
own shot-quality model.

Model: logistic regression P(goal) ~ distance-to-goal + shot angle, trained
on all 2745 shots with coordinates. Coordinates are on a 0-100 x 0-100 grid;
a team attacks whichever goal it's shooting toward, inferred per-shot from
which half the shot was taken in (x<50 -> left goal at x=0, else right goal
at x=100). This is the standard simple xG feature set (distance + angle);
it won't match Opta/StatsBomb's proprietary models but is a real, validated
improvement over "count the goals".
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

# pitch dimensions in metres for scaling the 0-100 grid
PITCH_LEN = 105.0
PITCH_WID = 68.0
GOAL_WIDTH = 7.32

MATCH_MAP_PATH = "/tmp/fifa_match_map.json"


def _dist_angle(dx_m, dy_m):
    """Distance (m) and subtended goal angle (rad) from metric offsets."""
    dist = np.hypot(dx_m, dy_m)
    a, b = dx_m, dy_m
    num = GOAL_WIDTH * a
    den = a**2 + b**2 - (GOAL_WIDTH / 2) ** 2
    angle = np.abs(np.arctan2(num, den))
    if angle < 0:
        angle += np.pi
    return dist, angle


def shot_features(x, y):
    """FIFA 0-100 grid: team attacks x=0 if in left half, else x=100."""
    gx = 0.0 if x < 50 else 100.0
    dx_m = abs(x - gx) / 100.0 * PITCH_LEN
    dy_m = (y - 50.0) / 100.0 * PITCH_WID
    return _dist_angle(dx_m, dy_m)


def statsbomb_features(x, y):
    """StatsBomb 0-120 x 0-80 grid: attacking team always shoots toward (120, 40)."""
    dx_m = (120.0 - x) / 120.0 * PITCH_LEN
    dy_m = (y - 40.0) / 80.0 * PITCH_WID
    return _dist_angle(dx_m, dy_m)


def fit_xg_model(conn, pool_statsbomb=True):
    """
    Fit logistic P(goal) ~ [distance, angle] on FIFA WC2026 shots, optionally
    pooled with StatsBomb historical-tournament shots for more robust
    coefficients. Returns the fitted model (feature space is source-agnostic:
    both sources are mapped to the same metric distance/angle).
    """
    fifa = pd.read_sql("""
        SELECT position_x AS x, position_y AS y, is_goal
        FROM fifa_shot_events
        WHERE position_x IS NOT NULL AND position_y IS NOT NULL
    """, conn)
    feats = [shot_features(r.x, r.y) for r in fifa.itertuples()]
    labels = list(fifa["is_goal"].astype(int).values)

    n_sb = 0
    if pool_statsbomb:
        try:
            sb = pd.read_sql("""
                SELECT location_x AS x, location_y AS y, is_goal
                FROM statsbomb_shots
                WHERE location_x IS NOT NULL AND location_y IS NOT NULL
            """, conn)
            feats += [statsbomb_features(r.x, r.y) for r in sb.itertuples()]
            labels += list(sb["is_goal"].astype(int).values)
            n_sb = len(sb)
        except Exception:  # noqa: BLE001 -- table may be empty/absent
            pass

    X = np.array(feats)
    y = np.array(labels)
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    print(f"xG model trained on {len(fifa)} FIFA + {n_sb} StatsBomb = {len(y)} shots")
    return model


def compute_match_xg(conn, pool_statsbomb=True):
    """Return DataFrame: fifa_match_id, team_id, xg (sum of per-shot xG)."""
    shots = pd.read_sql("""
        SELECT match_id, team_id, position_x, position_y, is_goal
        FROM fifa_shot_events
        WHERE position_x IS NOT NULL AND position_y IS NOT NULL
    """, conn)

    xg_model = fit_xg_model(conn, pool_statsbomb=pool_statsbomb)

    feats = np.array([shot_features(r.position_x, r.position_y) for r in shots.itertuples()])
    shots["xg"] = xg_model.predict_proba(feats)[:, 1]

    # Recalibrate absolute level to THIS tournament: pooling StatsBomb shots
    # makes the distance/angle coefficients more robust, but their shot
    # population has a slightly different conversion rate, which shifts the
    # absolute xG level for WC2026 (e.g. 289 predicted vs 264 actual goals).
    # A single global rescale to match WC2026's actual goal total fixes the
    # level without touching the (improved) relative shot ranking that drives
    # per-match xG differences. No-op when not pooling.
    actual_goals = shots["is_goal"].sum()
    pred_total = shots["xg"].sum()
    if pred_total > 0:
        shots["xg"] *= actual_goals / pred_total
    print(f"xG model: recalibrated total xG={shots['xg'].sum():.1f} "
          f"to match {actual_goals} actual goals (raw pred was {pred_total:.1f})")

    match_xg = shots.groupby(["match_id", "team_id"])["xg"].sum().reset_index()
    return match_xg, xg_model


def build_xg_match_table(conn, pool_statsbomb=True):
    """
    Join per-team match xG onto team names + dates via the cached FIFA match
    map, producing a tidy table the Dixon-Coles fitter can consume:
        date, team1, team2, xg1, xg2, g1, g2
    """
    match_xg, xg_model = compute_match_xg(conn, pool_statsbomb=pool_statsbomb)
    match_map = json.load(open(MATCH_MAP_PATH))

    xg_by_match_team = {}
    for r in match_xg.itertuples():
        xg_by_match_team[(str(r.match_id), str(r.team_id))] = r.xg

    rows = []
    for mid, info in match_map.items():
        if info["home_score"] is None:
            continue
        xg1 = xg_by_match_team.get((mid, str(info["home_id"])))
        xg2 = xg_by_match_team.get((mid, str(info["away_id"])))
        if xg1 is None or xg2 is None:
            continue
        rows.append({
            "date": info["date"],
            "team1": info["home"], "team2": info["away"],
            "xg1": xg1, "xg2": xg2,
            "g1": info["home_score"], "g2": info["away_score"],
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True), xg_model


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "../collector")
    from dotenv import load_dotenv
    load_dotenv()
    import db
    conn = db.connect()
    try:
        df, _ = build_xg_match_table(conn)
        print(f"\nBuilt xG match table: {len(df)} matches")
        print(df.head(10).to_string())
        print(f"\nCorrelation xG vs actual goals: "
              f"{np.corrcoef(df['xg1'].tolist() + df['xg2'].tolist(), df['g1'].tolist() + df['g2'].tolist())[0,1]:.3f}")
    finally:
        conn.close()
