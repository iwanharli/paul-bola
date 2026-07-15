"""
ESPN public site API collector -> db_boforecasting.

Free, no key required. Fills three gaps FIFA's official API left open:
  - starting XI (roster[].starter flag) -- confirmed populated post-match
  - team-level match stats: possession%, shots, corners, fouls, cards
  - structured bookmaker odds (moneyline/spread/total), no manual copy-paste

    GET /apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=YYYYMMDD
    GET /apis/site/v2/sports/soccer/fifa.world/summary?event=<id>

Usage:
    python espn_collect.py scoreboard <YYYYMMDD>   # list event ids for a date
    python espn_collect.py match <event_id>        # pull rosters/stats/odds
"""
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

import db

from config import ESPN_BASE as BASE
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_scoreboard(date_str: str):
    resp = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("events", [])


def get_summary(event_id: str):
    resp = requests.get(f"{BASE}/summary", params={"event": event_id}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect_match(conn, event_id: str):
    data = get_summary(event_id)
    eid = int(event_id)

    rosters = data.get("rosters", [])
    roster_count = 0
    for r in rosters:
        team_name = r.get("team", {}).get("displayName", "")
        for p in r.get("roster", []):
            athlete = p.get("athlete", {})
            if not athlete.get("id"):
                continue
            db.upsert_composite(conn, "espn_match_rosters", {
                "espn_event_id": eid,
                "espn_athlete_id": int(athlete["id"]),
                "team_name": team_name,
                "player_name": athlete.get("displayName", ""),
                "jersey": p.get("jersey"),
                "starter": p.get("starter", False),
                "raw": p,
            }, ["espn_event_id", "espn_athlete_id"])
            roster_count += 1

    box = data.get("boxscore", {})
    stats_count = 0
    for t in box.get("teams", []):
        team_name = t.get("team", {}).get("displayName", "")
        stat_map = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}

        def num(key):
            v = stat_map.get(key)
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        db.upsert_composite(conn, "espn_match_team_stats", {
            "espn_event_id": eid,
            "team_name": team_name,
            "possession_pct": num("possessionPct"),
            "total_shots": num("totalShots"),
            "fouls_committed": num("foulsCommitted"),
            "yellow_cards": num("yellowCards"),
            "red_cards": num("redCards"),
            "offsides": num("offsides"),
            "won_corners": num("wonCorners"),
            "saves": num("saves"),
            "raw": t,
        }, ["espn_event_id", "team_name"])
        stats_count += 1

    odds_count = 0
    for o in data.get("odds", []):
        provider = o.get("provider", {}).get("name", "unknown")
        db.upsert_composite(conn, "espn_match_odds", {
            "espn_event_id": eid,
            "provider": provider,
            "details": o.get("details"),
            "over_under": o.get("overUnder"),
            "spread": o.get("spread"),
            "home_moneyline": (o.get("homeTeamOdds") or {}).get("moneyLine"),
            "away_moneyline": (o.get("awayTeamOdds") or {}).get("moneyLine"),
            "raw": o,
        }, ["espn_event_id", "provider"])
        odds_count += 1

    conn.commit()
    db.log_collection(conn, "espn", "match", f"event:{event_id}", "success",
                       f"{roster_count} roster rows, {stats_count} team stats, {odds_count} odds rows")
    print(f"event {event_id}: {roster_count} roster rows, {stats_count} team stats rows, {odds_count} odds rows")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "scoreboard":
        events = get_scoreboard(sys.argv[2])
        for e in events:
            print(e["id"], e.get("name"))
        return

    conn = db.connect()
    try:
        if cmd == "match":
            collect_match(conn, sys.argv[2])
        else:
            print(__doc__)
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
