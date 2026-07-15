"""
Collect penalty-shootout kick-by-kick history from StatsBomb open data
(period=5 events) across WC2022/Euro2024/Copa2024 -- the same tournaments
already pulled for statsbomb_shots_collect.py. Used to replace the model's
hardcoded 50/50 shootout assumption with a real goalkeeper save rate where
the sample supports it.

Usage:
    python shootout_collect.py
"""
import warnings

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()

from statsbombpy import sb
import db

TOURNAMENTS = [
    ("WC2022", 43, 106),
    ("Euro2024", 55, 282),
    ("Copa2024", 223, 282),
]


def collect():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE shootout_history RESTART IDENTITY")
        conn.commit()

        total_kicks = 0
        total_shootouts = 0
        for name, cid, sid in TOURNAMENTS:
            matches = sb.matches(competition_id=cid, season_id=sid)
            print(f"{name}: scanning {len(matches)} matches for shootouts")
            for _, m in matches.iterrows():
                match_id = int(m["match_id"])
                try:
                    ev = sb.events(match_id=match_id)
                except Exception as exc:  # noqa: BLE001
                    db.log_collection(conn, "statsbomb", "shootout", f"match:{match_id}", "error", str(exc))
                    continue

                shootout = ev[ev["period"] == 5]
                if shootout.empty:
                    continue
                total_shootouts += 1

                # one consistent goalkeeper per team for the whole shootout
                gk_rows = shootout[shootout["type"] == "Goal Keeper"]
                keeper_by_team = dict(zip(gk_rows["team"], gk_rows["player"]))

                shots = shootout[shootout["type"] == "Shot"].reset_index(drop=True)
                print(f"  {name} match {match_id}: {m['home_team']} vs {m['away_team']} "
                      f"-- {len(shots)} shootout kicks")

                for order, s in shots.iterrows():
                    kicking_team = s["team"]
                    opposing_team = next((t for t in keeper_by_team if t != kicking_team), None)
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO shootout_history
                                (tournament, match_id, kick_order, kicking_team, kicker_name,
                                 outcome, opposing_team, opposing_goalkeeper)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (match_id, kick_order) DO NOTHING
                        """, (name, match_id, int(order), kicking_team, s["player"],
                              s["shot_outcome"], opposing_team, keeper_by_team.get(opposing_team)))
                    total_kicks += 1
                conn.commit()

        db.log_collection(conn, "statsbomb", "shootout", "all_tournaments", "success",
                           f"{total_shootouts} shootouts, {total_kicks} kicks")
        print(f"\nStored {total_kicks} kicks across {total_shootouts} shootouts")
    finally:
        conn.close()


if __name__ == "__main__":
    collect()
