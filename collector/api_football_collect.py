"""
API-FOOTBALL / API-Sports collector -> provider_match_context.

Requires registration/API key:
    API_FOOTBALL_KEY=...

Optional env:
    API_FOOTBALL_LEAGUE=1
    API_FOOTBALL_SEASON=2026

Stores fixtures, odds, lineups, and injuries when available on the configured
plan. Missing key logs a partial/skipped run.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

import db
from config import COMPETITION

BASE = "https://v3.football.api-sports.io"


def _headers():
    return {"x-apisports-key": os.environ["API_FOOTBALL_KEY"]}


def _get(path, **params):
    resp = requests.get(f"{BASE}{path}", params={k: v for k, v in params.items() if v is not None}, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data.get("response", [])


def _upsert_context(conn, endpoint, external_id, raw, match_date=None, home=None, away=None):
    db.upsert_composite(conn, "provider_match_context", {
        "competition": COMPETITION,
        "provider": "api-football",
        "endpoint": endpoint,
        "external_id": str(external_id),
        "match_date": match_date,
        "home_team": home,
        "away_team": away,
        "raw": raw,
    }, ["provider", "endpoint", "external_id"])


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


def _store_fixture_bundle(conn, fixture_row):
    fixture = fixture_row.get("fixture") or {}
    teams = fixture_row.get("teams") or {}
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    fixture_id = fixture.get("id")
    match_date = (fixture.get("date") or "")[:10] or None
    _upsert_context(conn, "fixtures", fixture_id, fixture_row, match_date, home, away)
    return fixture_id, match_date, home, away


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        if not os.environ.get("API_FOOTBALL_KEY"):
            db.log_collection(conn, "api-football", "context", "upcoming_worldcup", "partial", "missing API_FOOTBALL_KEY")
            print("Skipping API-Football: API_FOOTBALL_KEY is not set")
            return

        league = os.environ.get("API_FOOTBALL_LEAGUE", "1")
        season = os.environ.get("API_FOOTBALL_SEASON", "2026")
        fixtures = []
        for date in _target_dates(conn):
            fixtures.extend(_get("/fixtures", league=league, season=season, date=date))

        detail_count = 0
        for row in fixtures:
            fixture_id, match_date, home, away = _store_fixture_bundle(conn, row)
            if not fixture_id:
                continue
            for endpoint, path in (
                ("lineups", "/fixtures/lineups"),
                ("injuries", "/injuries"),
                ("odds", "/odds"),
            ):
                try:
                    params = {"fixture": fixture_id}
                    if endpoint == "injuries":
                        params.update({"league": league, "season": season})
                    for item in _get(path, **params):
                        external_id = f"{fixture_id}:{endpoint}:{item.get('team', {}).get('id') or item.get('bookmaker', {}).get('id') or detail_count}"
                        _upsert_context(conn, endpoint, external_id, item, match_date, home, away)
                        detail_count += 1
                except Exception as exc:  # noqa: BLE001
                    db.log_collection(conn, "api-football", endpoint, f"fixture:{fixture_id}", "partial", str(exc))

        conn.commit()
        db.log_collection(conn, "api-football", "context", "upcoming_worldcup", "success", f"{len(fixtures)} fixtures, {detail_count} detail rows")
        print(f"API-Football stored {len(fixtures)} fixtures and {detail_count} detail rows")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "api-football", "context", "upcoming_worldcup", "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
