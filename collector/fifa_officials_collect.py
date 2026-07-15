"""
FIFA match officials collector -> db_boforecasting.fifa_match_officials.

Officials are embedded in the FIFA calendar endpoint (already fetched by
fifa_collect), so this is free -- no extra API calls beyond one calendar pull.
Previously this was a one-off inline script; made a proper collector so the
orchestrator can refresh it.

Usage:
    python fifa_officials_collect.py
"""
import requests
from dotenv import load_dotenv

load_dotenv()

import db

from config import FIFA_COMPETITION_ID as COMPETITION_ID, FIFA_SEASON_ID as SEASON_ID

BASE = "https://api.fifa.com/api/v3"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _localized(value):
    if isinstance(value, list) and value:
        return value[0].get("Description") if isinstance(value[0], dict) else None
    if isinstance(value, dict):
        return value.get("Description")
    return value


def get_calendar_matches():
    r = requests.get(f"{BASE}/calendar/matches",
                     params={"idSeason": SEASON_ID, "idCompetition": COMPETITION_ID, "count": 200},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["Results"]


def store_match_index(conn, match):
    home = match.get("Home") or {}
    away = match.get("Away") or {}
    match_date = (match.get("Date") or match.get("LocalDate") or "")[:10] or None
    db.upsert(conn, "fifa_match_index", {
        "fifa_match_id": int(match["IdMatch"]),
        "id_stage": match.get("IdStage"),
        "match_date": match_date,
        "kickoff_utc": match.get("Date"),
        "home_team": _localized(home.get("TeamName")),
        "away_team": _localized(away.get("TeamName")),
        "ground": _localized((match.get("Stadium") or {}).get("Name")) or _localized(match.get("StadiumName")),
        "status": _localized(match.get("MatchStatus")) or _localized(match.get("Status")),
        "raw": match,
    }, "fifa_match_id")


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        matches = get_calendar_matches()

        count = 0
        for m in matches:
            store_match_index(conn, m)
            match_id = int(m["IdMatch"])
            for o in m.get("Officials", []):
                db.upsert_composite(conn, "fifa_match_officials", {
                    "fifa_match_id": match_id,
                    "official_id": int(o["OfficialId"]),
                    "name": _localized(o.get("Name")),
                    "role": _localized(o.get("TypeLocalized")) if o.get("TypeLocalized") else None,
                    "country": o.get("IdCountry"),
                    "raw": o,
                }, ["fifa_match_id", "official_id"])
                count += 1
        conn.commit()
        db.log_collection(conn, "fifa", "officials", "all_matches", "success", f"{count} official entries")
        print(f"Stored {count} official rows across {len(matches)} matches")
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
