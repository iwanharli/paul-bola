"""
World Cup 2026 fixtures/results collector -> db_boforecasting.

Source: openfootball/worldcup.json (free, no API key, community-maintained,
manually updated ~daily -- NOT a live feed). Covers full bracket: group stage
through final, with scores and goal scorers.

    https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json

Usage:
    python worldcup_collect.py
"""
import requests
from dotenv import load_dotenv

load_dotenv()

import db

SOURCE_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"


def _score(match: dict, key: str, idx: int):
    pair = match.get("score", {}).get(key)
    return pair[idx] if pair else None


def collect():
    resp = requests.get(SOURCE_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    matches = payload.get("matches", [])
    print(f"Fetched {len(matches)} matches for {payload.get('name')}")

    conn = db.connect()
    try:
        for i, m in enumerate(matches, start=1):
            db.upsert_composite(conn, "worldcup_matches", {
                "tournament": payload.get("name", "World Cup 2026"),
                "match_num": m.get("num", i),
                "round": m.get("round"),
                "match_date": m.get("date"),
                "match_time": m.get("time"),
                "team1": m.get("team1"),
                "team2": m.get("team2"),
                "score_ht_team1": _score(m, "ht", 0),
                "score_ht_team2": _score(m, "ht", 1),
                "score_ft_team1": _score(m, "ft", 0),
                "score_ft_team2": _score(m, "ft", 1),
                "score_et_team1": _score(m, "et", 0),
                "score_et_team2": _score(m, "et", 1),
                "score_pens_team1": _score(m, "pens", 0),
                "score_pens_team2": _score(m, "pens", 1),
                "goals1": m.get("goals1", []),
                "goals2": m.get("goals2", []),
                "ground": m.get("ground"),
                "raw": m,
            }, ["tournament", "match_num"],
                # never let openfootball's not-yet-updated NULL score wipe a
                # result the faster live fallback (ESPN) already wrote
                coalesce_cols=["score_ft_team1", "score_ft_team2",
                               "score_et_team1", "score_et_team2",
                               "score_pens_team1", "score_pens_team2"])
        conn.commit()
        db.log_collection(conn, "openfootball", "worldcup_matches", "World Cup 2026", "success",
                           f"{len(matches)} matches")
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    collect()
