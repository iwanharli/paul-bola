"""
American Soccer Analysis (ASA) collector -> db_boforecasting.

Free public API, no key required. Fills the MLS gap Understat doesn't cover
-- specifically needed for Lionel Messi's current club form (Inter Miami CF).

    GET https://app.americansocceranalysis.com/api/v1/mls/players?season_name=<season>
    GET https://app.americansocceranalysis.com/api/v1/mls/players/xgoals?season_name=<season>&player_id=<id>

Usage:
    python asa_collect.py season <season>          # all players' xG for a season, e.g. 2026
    python asa_collect.py player <name_substring> <season>
"""
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

import db

BASE = "https://app.americansocceranalysis.com/api/v1/mls"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def find_players(name_substring: str):
    resp = requests.get(f"{BASE}/players", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    players = resp.json()
    return [p for p in players if name_substring.lower() in p.get("player_name", "").lower()]


def get_games(season: str):
    resp = requests.get(f"{BASE}/games", params={"season_name": season}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect_player_games(conn, player_id: str, season: str):
    resp = requests.get(f"{BASE}/players/xgoals", params={
        "season_name": season, "player_id": player_id, "split_by_games": "true",
    }, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    rows = resp.json()

    games = {g["game_id"]: g for g in get_games(season)}

    for r in rows:
        game = games.get(r["game_id"], {})
        db.upsert_composite(conn, "asa_player_game_xg", {
            "player_id": r["player_id"],
            "game_id": r["game_id"],
            "team_id": r["team_id"],
            "season_name": season,
            "game_date_utc": game.get("date_time_utc"),
            "minutes_played": r.get("minutes_played"),
            "shots": r.get("shots"),
            "shots_on_target": r.get("shots_on_target"),
            "goals": r.get("goals"),
            "xgoals": r.get("xgoals"),
            "key_passes": r.get("key_passes"),
            "primary_assists": r.get("primary_assists"),
            "xassists": r.get("xassists"),
            "raw": r,
        }, ["player_id", "game_id"])
    conn.commit()
    db.log_collection(conn, "asa", "player_game_xg", f"player:{player_id}/season:{season}", "success",
                       f"{len(rows)} games")
    print(f"Stored {len(rows)} per-game rows for player {player_id}")


def collect_season_xg(conn, season: str, player_id: str | None = None):
    params = {"season_name": season}
    if player_id:
        params["player_id"] = player_id
    resp = requests.get(f"{BASE}/players/xgoals", params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    rows = resp.json()

    # Need player names too, since the xgoals endpoint doesn't include them
    all_players = requests.get(f"{BASE}/players", headers=HEADERS, timeout=30).json()
    name_by_id = {p["player_id"]: p["player_name"] for p in all_players}

    for r in rows:
        db.upsert_composite(conn, "asa_player_season_xg", {
            "player_id": r["player_id"],
            "team_id": r["team_id"],
            "season_name": season,
            "player_name": name_by_id.get(r["player_id"], "Unknown"),
            "general_position": r.get("general_position"),
            "minutes_played": r.get("minutes_played"),
            "shots": r.get("shots"),
            "shots_on_target": r.get("shots_on_target"),
            "goals": r.get("goals"),
            "xgoals": r.get("xgoals"),
            "key_passes": r.get("key_passes"),
            "primary_assists": r.get("primary_assists"),
            "xassists": r.get("xassists"),
            "goals_plus_primary_assists": r.get("goals_plus_primary_assists"),
            "xgoals_plus_xassists": r.get("xgoals_plus_xassists"),
            "raw": r,
        }, ["player_id", "season_name"])
    conn.commit()
    db.log_collection(conn, "asa", "players_xgoals", f"season:{season}", "success", f"{len(rows)} players")
    print(f"Stored {len(rows)} player-season xG rows for {season}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    conn = db.connect()
    try:
        if cmd == "season":
            season = sys.argv[2]
            collect_season_xg(conn, season)
        elif cmd == "player":
            name_substring, season = sys.argv[2], sys.argv[3]
            matches = find_players(name_substring)
            for p in matches:
                print(p["player_id"], p["player_name"])
                collect_season_xg(conn, season, player_id=p["player_id"])
                collect_player_games(conn, p["player_id"], season)
        else:
            print(__doc__)
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
