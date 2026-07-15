"""
FIFA official public match-centre API collector -> db_boforecasting.

Source: api.fifa.com (no key required, undocumented but publicly reachable).
Fills the gap no other free source covers: shot-by-shot event data with pitch
coordinates for World Cup 2026 matches, which we'll use to compute our own xG
(no source gives ready-made WC2026 xG).

    GET /api/v3/calendar/matches?idSeason=<season>&idCompetition=<comp>&count=200
    GET /api/v3/timelines/<comp>/<season>/<stage>/<match>?language=en-GB

Usage:
    python fifa_collect.py calendar                 # list + cache all match metadata
    python fifa_collect.py shots <team_name_filter>  # pull shot events for finished matches
                                                      # involving a team (e.g. "Argentina")
    python fifa_collect.py shots all                 # pull shot events for every finished match
"""
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

import db

BASE = "https://api.fifa.com/api/v3"
HEADERS = {"User-Agent": "Mozilla/5.0"}
COMPETITION_ID = 17
SEASON_ID = 285023

SHOT_EVENT_TYPES = {12, 0}  # 12 = Attempt at Goal (non-goal outcome), 0 = Goal!


def get_calendar():
    resp = requests.get(f"{BASE}/calendar/matches", params={
        "idSeason": SEASON_ID, "idCompetition": COMPETITION_ID, "count": 200,
    }, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("Results", [])


def get_timeline(id_stage: int, match_id: int):
    resp = requests.get(
        f"{BASE}/timelines/{COMPETITION_ID}/{SEASON_ID}/{id_stage}/{match_id}",
        params={"language": "en-GB"}, headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("Event", [])


def collect_shots(team_filter: str | None):
    conn = db.connect()
    try:
        matches = get_calendar()
        finished = [m for m in matches if m["Home"].get("Score") is not None]

        if team_filter and team_filter.lower() != "all":
            def involves(m):
                home = m["Home"]["TeamName"][0]["Description"]
                away = m["Away"]["TeamName"][0]["Description"]
                return team_filter.lower() in (home.lower(), away.lower())
            finished = [m for m in finished if involves(m)]

        print(f"Pulling shot events for {len(finished)} finished matches")

        total_shots = 0
        for m in finished:
            match_id = int(m["IdMatch"])
            id_stage = int(m["IdStage"])
            try:
                events = get_timeline(id_stage, match_id)
            except Exception as exc:  # noqa: BLE001
                db.log_collection(conn, "fifa", "timeline", f"match:{match_id}", "error", str(exc))
                continue

            for e in events:
                if e.get("Type") not in SHOT_EVENT_TYPES:
                    continue
                desc = (e.get("EventDescription") or [{}])[0].get("Description", "")
                is_goal = e.get("Type") == 0
                db.upsert(conn, "fifa_shot_events", {
                    "event_id": int(e["EventId"]),
                    "match_id": match_id,
                    "team_id": int(e["IdTeam"]) if e.get("IdTeam") else None,
                    "player_id": int(e["IdPlayer"]) if e.get("IdPlayer") else None,
                    "minute": e.get("MatchMinute"),
                    "period": e.get("Period"),
                    "position_x": e.get("PositionX"),
                    "position_y": e.get("PositionY"),
                    "event_type": e.get("Type"),
                    "event_type_desc": (e.get("TypeLocalized") or [{}])[0].get("Description"),
                    "description": desc,
                    "is_goal": is_goal,
                    "raw": e,
                }, conflict_col="event_id")
                total_shots += 1
            conn.commit()
            time.sleep(0.3)

        db.log_collection(conn, "fifa", "shots", team_filter or "all", "success", f"{total_shots} shot events")
        print(f"Stored {total_shots} shot events")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "calendar":
        matches = get_calendar()
        print(f"{len(matches)} matches in calendar")
    elif cmd == "shots":
        team_filter = sys.argv[2] if len(sys.argv) > 2 else "all"
        collect_shots(team_filter)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
