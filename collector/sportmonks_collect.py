"""
Sportmonks Football API collector -> provider_match_context.

Requires registration/API token:
    SPORTMONKS_TOKEN=...

Optional env:
    SPORTMONKS_BASE=https://api.sportmonks.com/v3/football

Stores date fixtures with rich includes when the plan allows them. Because
Sportmonks coverage/plan entitlements vary, raw data is kept in a generic table.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

import db
from config import COMPETITION

BASE = os.environ.get("SPORTMONKS_BASE", "https://api.sportmonks.com/v3/football")
INCLUDES = "participants;league;season;round;venue;state;lineups;metadata;referees;odds;statistics"


def _get(path, **params):
    token = os.environ["SPORTMONKS_TOKEN"]
    params = {"api_token": token, **params}
    resp = requests.get(f"{BASE}{path}", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("message") and not data.get("data"):
        raise RuntimeError(data.get("message"))
    return data.get("data", [])


def _target_dates(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT match_date
            FROM worldcup_matches
            WHERE score_ft_team1 IS NULL
               OR round IN ('Semi-final', 'Match for third place', 'Final')
            ORDER BY match_date
        """)
        return [row[0].isoformat() for row in cur.fetchall()]


def _names(fixture):
    participants = fixture.get("participants") or []
    home = away = None
    for row in participants:
        meta = row.get("meta") or {}
        if meta.get("location") == "home":
            home = row.get("name")
        elif meta.get("location") == "away":
            away = row.get("name")
    return home, away


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        if not os.environ.get("SPORTMONKS_TOKEN"):
            db.log_collection(conn, "sportmonks", "fixtures", "upcoming_worldcup", "partial", "missing SPORTMONKS_TOKEN")
            print("Skipping Sportmonks: SPORTMONKS_TOKEN is not set")
            return

        count = 0
        for date in _target_dates(conn):
            fixtures = _get(f"/fixtures/date/{date}", include=INCLUDES)
            for fixture in fixtures:
                home, away = _names(fixture)
                db.upsert_composite(conn, "provider_match_context", {
                    "competition": COMPETITION,
                    "provider": "sportmonks",
                    "endpoint": "fixtures",
                    "external_id": str(fixture.get("id")),
                    "match_date": date,
                    "home_team": home,
                    "away_team": away,
                    "raw": fixture,
                }, ["provider", "endpoint", "external_id"])
                count += 1
        conn.commit()
        db.log_collection(conn, "sportmonks", "fixtures", "upcoming_worldcup", "success", f"{count} fixtures")
        print(f"Sportmonks stored {count} fixtures")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "sportmonks", "fixtures", "upcoming_worldcup", "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
