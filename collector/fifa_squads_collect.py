"""
FIFA official squad list collector -> db_boforecasting.fifa_squads.

Pulls the 26-player squad (IdPlayer, name, shirt number, position) for a team
from the /live/football match endpoint (squad data is embedded per-match, so
we just need any one match involving that team this tournament).

Usage:
    python fifa_squads_collect.py <team_name>   # e.g. "Argentina", "England"
"""
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

import db

BASE = "https://api.fifa.com/api/v3"
HEADERS = {"User-Agent": "Mozilla/5.0"}
COMPETITION_ID = 17
SEASON_ID = 285023


def get_calendar():
    resp = requests.get(f"{BASE}/calendar/matches", params={
        "idSeason": SEASON_ID, "idCompetition": COMPETITION_ID, "count": 200,
    }, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("Results", [])


def collect_squad(conn, team_name: str):
    matches = get_calendar()
    match = next(
        (m for m in matches
         if team_name.lower() in (m["Home"]["TeamName"][0]["Description"].lower(),
                                   m["Away"]["TeamName"][0]["Description"].lower())),
        None,
    )
    if not match:
        print(f"No match found involving {team_name}")
        return

    match_id, id_stage = match["IdMatch"], match["IdStage"]
    resp = requests.get(f"{BASE}/live/football/{COMPETITION_ID}/{SEASON_ID}/{id_stage}/{match_id}",
                         headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    for side in ("HomeTeam", "AwayTeam"):
        team = data[side]
        side_name = team["TeamName"][0]["Description"]
        if team_name.lower() != side_name.lower():
            continue
        team_id = int(team["IdTeam"])
        players = team.get("Players", [])
        for p in players:
            db.upsert_composite(conn, "fifa_squads", {
                "fifa_player_id": int(p["IdPlayer"]),
                "fifa_team_id": team_id,
                "player_name": p["PlayerName"][0]["Description"],
                "shirt_number": p.get("ShirtNumber"),
                "position": p.get("Position"),
                "raw": p,
            }, ["fifa_player_id", "fifa_team_id"])
        conn.commit()
        db.log_collection(conn, "fifa", "squad", team_name, "success", f"{len(players)} players")
        print(f"Stored {len(players)} players for {side_name}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    conn = db.connect()
    try:
        collect_squad(conn, sys.argv[1])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
