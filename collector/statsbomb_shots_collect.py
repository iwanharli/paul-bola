"""
Collect StatsBomb open-data shots (location + goal outcome + their xG) from
recent international tournaments, to enlarge the training set for our own
coordinate-based xG model.

Usage:
    python statsbomb_shots_collect.py
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
        # idempotent: clear and repopulate (source is static open data)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE statsbomb_shots RESTART IDENTITY")
        conn.commit()

        total = 0
        for name, cid, sid in TOURNAMENTS:
            matches = sb.matches(competition_id=cid, season_id=sid)
            print(f"{name}: {len(matches)} matches")
            for match_id in matches["match_id"]:
                try:
                    ev = sb.events(match_id=match_id)
                except Exception as exc:  # noqa: BLE001
                    db.log_collection(conn, "statsbomb", "shots", f"match:{match_id}", "error", str(exc))
                    continue
                shots = ev[ev["type"] == "Shot"]
                for s in shots.itertuples():
                    loc = getattr(s, "location", None)
                    if not isinstance(loc, list) or len(loc) < 2:
                        continue
                    outcome = getattr(s, "shot_outcome", None)
                    xg = getattr(s, "shot_statsbomb_xg", None)
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO statsbomb_shots
                                (competition, match_id, location_x, location_y, is_goal, statsbomb_xg)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (name, int(match_id), float(loc[0]), float(loc[1]),
                              outcome == "Goal",
                              float(xg) if xg == xg and xg is not None else None))  # xg==xg filters NaN
                    total += 1
                conn.commit()
            print(f"  {name} done, running total {total} shots")

        db.log_collection(conn, "statsbomb", "shots", "all_tournaments", "success", f"{total} shots")
        print(f"\nStored {total} StatsBomb shots")
    finally:
        conn.close()


if __name__ == "__main__":
    collect()
