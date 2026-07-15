"""
Player "anytime goalscorer" model for the England vs Argentina semifinal,
with penalties handled separately.

The Dixon-Coles model gives each TEAM an expected-goals figure. We split it
into OPEN-PLAY and PENALTY components:

  - open-play goals are distributed among players by their share of the team's
    open-play tournament xG (penalty shots removed so they aren't double-counted)
  - penalty goals go entirely to the team's designated penalty taker

    player exp goals = open_expected * open_xg_share
                       (+ penalty_expected  if this player is the taker)
    P(anytime scorer) = 1 - exp(-player exp goals)          [Poisson]

Designated takers (DEFAULT, user-specified): England=Kane, Argentina=Messi.
HONEST DATA NOTE: in THIS tournament, Argentina's one penalty was scored by
Lautaro Martinez, not Messi -- so the "Messi takes pens" assumption is a
real-world prior overriding the 6-match sample, flagged rather than hidden.

Availability: players marked out/suspended in player_availability are dropped
(Henderson out, Quansah suspended).

Honest limits (also in README):
  - Open-play shares are TOURNAMENT xG based (6 matches) -- small sample,
    assumes role continues.
  - Penalty rate is a shrink of each team's tiny tournament count toward the
    tournament-wide 0.074 pens/team/match; still high variance.
  - Doesn't blend club form (cross-source per-player joins are name-based).
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db
from xg_model import build_xg_match_table, fit_xg_model, shot_features
from final_predict import fit_all, score_matrix, BLEND_ALPHA

FIFA_TEAM = {"Argentina": 43922, "England": 43942, "Spain": 43969}

# Designated penalty takers (user-specified; see module docstring note that the
# 6-match sample actually shows Lautaro took Argentina's only pen).
DESIGNATED_TAKER = {"Argentina": "messi", "England": "kane", "Spain": "oyarzabal"}

PEN_XG = 0.76             # standard penalty conversion / xG value
TOURNAMENT_PEN_RATE = 0.074  # penalty goals per team per match, all 101 matches
PEN_PRIOR_STRENGTH = 2.0  # pseudo-matches of shrinkage toward the tournament rate


def penalty_takers_tournament(conn):
    """Per-player count of penalties SCORED in the tournament (openfootball flags)."""
    df = pd.read_sql("""
        SELECT goals1, goals2 FROM worldcup_matches WHERE score_ft_team1 IS NOT NULL
    """, conn)
    counts = {}
    for _, row in df.iterrows():
        for g in (row["goals1"] or []) + (row["goals2"] or []):
            if g.get("penalty"):
                counts[g["name"].lower()] = counts.get(g["name"].lower(), 0) + 1
    return counts


def team_penalty_rate(conn, team_name):
    """Shrunk estimate of penalty goals per match for a team."""
    df = pd.read_sql("""
        SELECT team1, team2, goals1, goals2 FROM worldcup_matches
        WHERE score_ft_team1 IS NOT NULL
          AND (team1 = %(t)s OR team2 = %(t)s)
    """, conn, params={"t": team_name})
    pens = matches = 0
    for _, row in df.iterrows():
        matches += 1
        goals = row["goals1"] if row["team1"] == team_name else row["goals2"]
        pens += sum(1 for g in (goals or []) if g.get("penalty"))
    return (pens + PEN_PRIOR_STRENGTH * TOURNAMENT_PEN_RATE) / (matches + PEN_PRIOR_STRENGTH)


def player_tournament_xg(conn):
    """Per-player summed xG across the tournament, from FIFA shot coordinates."""
    shots = pd.read_sql("""
        SELECT e.player_id, e.team_id, e.position_x, e.position_y, e.is_goal,
               s.player_name
        FROM fifa_shot_events e
        JOIN fifa_squads s ON s.fifa_player_id = e.player_id
        WHERE e.position_x IS NOT NULL
    """, conn)
    model = fit_xg_model(conn, pool_statsbomb=True)
    feats = np.array([shot_features(r.position_x, r.position_y) for r in shots.itertuples()])
    shots["xg"] = model.predict_proba(feats)[:, 1]
    agg = shots.groupby(["player_id", "player_name", "team_id"]).agg(
        shots=("xg", "size"), goals=("is_goal", "sum"), xg=("xg", "sum")
    ).reset_index()
    return agg


def unavailable_players(conn):
    df = pd.read_sql("""
        SELECT player_name FROM player_availability
        WHERE status IN ('out', 'suspended')
    """, conn)
    return set(df["player_name"].str.lower())


def scorer_probs(team_name, team_expected_goals, player_xg, unavailable,
                 pen_counts, pen_rate):
    tid = FIFA_TEAM[team_name]
    sub = player_xg[player_xg["team_id"] == tid].copy()

    def is_out(name):
        n = name.lower()
        return any(u.split()[-1] in n for u in unavailable if u)
    sub = sub[~sub["player_name"].apply(is_out)]

    # remove each player's tournament PENALTY xG so open-play shares are fair
    # (penalties they took won't necessarily recur to them; the designated
    # taker gets the future penalty mass instead).
    def pens_taken(name):
        n = name.lower()
        return next((c for who, c in pen_counts.items() if who.split()[-1] in n), 0)
    sub["pen_taken"] = sub["player_name"].apply(pens_taken)
    sub["open_xg"] = (sub["xg"] - sub["pen_taken"] * PEN_XG).clip(lower=0.0)
    sub = sub[sub["open_xg"] > 0]

    # split team expected goals into open-play + penalty
    penalty_expected = min(pen_rate, team_expected_goals)
    open_expected = team_expected_goals - penalty_expected

    total_open = sub["open_xg"].sum()
    sub["open_share"] = sub["open_xg"] / total_open
    sub["exp_goals_match"] = open_expected * sub["open_share"]

    # assign penalty mass to the designated taker (loose last-name match)
    taker_key = DESIGNATED_TAKER[team_name]
    is_taker = sub["player_name"].str.lower().str.contains(taker_key)
    sub.loc[is_taker, "exp_goals_match"] += penalty_expected
    sub["is_taker"] = is_taker

    sub["p_anytime"] = 1 - np.exp(-sub["exp_goals_match"])
    return sub.sort_values("p_anytime", ascending=False)


def main():
    conn = db.connect()
    try:
        xg_df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
        elo_map = dict(zip(elo["team_name"], elo["elo"]))
        # same xG/goals blend as final_predict, so team expected goals are
        # consistent between the match model and the scorer model
        xg_df = xg_df.copy()
        xg_df["xg1"] = BLEND_ALPHA * xg_df["xg1"] + (1 - BLEND_ALPHA) * xg_df["g1"]
        xg_df["xg2"] = BLEND_ALPHA * xg_df["xg2"] + (1 - BLEND_ALPHA) * xg_df["g2"]
        attack, defense, team_idx = fit_all(xg_df, elo_map)
        _, lam_arg, mu_eng = score_matrix(attack, defense, team_idx, "Argentina", "England")

        player_xg = player_tournament_xg(conn)
        unavailable = unavailable_players(conn)
        pen_counts = penalty_takers_tournament(conn)
        pen_rate = {t: team_penalty_rate(conn, t) for t in ("Argentina", "England")}
    finally:
        conn.close()

    print(f"\nPredicted team goals (90'): Argentina {lam_arg:.2f}, England {mu_eng:.2f}")
    print(f"Unavailable (dropped): {', '.join(unavailable) or 'none'}")
    print(f"Penalty rate/match (shrunk): "
          f"Argentina {pen_rate['Argentina']:.3f}, England {pen_rate['England']:.3f}")
    print(f"Designated takers: {DESIGNATED_TAKER}")

    for team, exp_goals in [("Argentina", lam_arg), ("England", mu_eng)]:
        sub = scorer_probs(team, exp_goals, player_xg, unavailable, pen_counts, pen_rate[team])
        print(f"\n=== {team} — anytime goalscorer probabilities (penalty-aware) ===")
        print(f"{'Player':24s} {'WC xG':>6s} {'WC gls':>6s} {'P(scores)':>9s}")
        for r in sub.head(8).itertuples():
            tag = "  <- pen taker" if r.is_taker else ""
            print(f"{r.player_name:24s} {r.xg:6.2f} {int(r.goals):6d} {r.p_anytime:8.1%}{tag}")


if __name__ == "__main__":
    main()
