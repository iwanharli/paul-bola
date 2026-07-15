"""
football-data.org collector -> football_data_matches + optional h2h_history.

Requires registration/API key:
    FOOTBALL_DATA_TOKEN=...

Optional env:
    FOOTBALL_DATA_COMPETITION=WC

Useful for fixtures/results/scorers/referee fallback. It also attempts H2H
enrichment for currently upcoming World Cup pairs when team IDs are available.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

import db
from source_utils import pair_matches, parse_date

BASE = "https://api.football-data.org/v4"


def _headers():
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    return {"X-Auth-Token": token} if token else {}


def _get(path, **params):
    resp = requests.get(f"{BASE}{path}", params={k: v for k, v in params.items() if v is not None}, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _store_match(conn, match):
    score = match.get("score", {}).get("fullTime") or {}
    db.upsert(conn, "football_data_matches", {
        "fd_match_id": int(match["id"]),
        "competition": (match.get("competition") or {}).get("code") or (match.get("competition") or {}).get("name"),
        "season": str((match.get("season") or {}).get("id") or ""),
        "match_date": parse_date(match.get("utcDate")),
        "kickoff_utc": match.get("utcDate"),
        "stage": match.get("stage"),
        "status": match.get("status"),
        "home_team": (match.get("homeTeam") or {}).get("name"),
        "away_team": (match.get("awayTeam") or {}).get("name"),
        "home_score": score.get("home"),
        "away_score": score.get("away"),
        "referees": match.get("referees", []),
        "raw": match,
    }, "fd_match_id")


def _competition_teams():
    comp = os.environ.get("FOOTBALL_DATA_COMPETITION", "WC")
    try:
        data = _get(f"/competitions/{comp}/teams")
    except requests.HTTPError:
        return {}
    return {team.get("name"): team.get("id") for team in data.get("teams", []) if team.get("id")}


def _upcoming_pairs(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT team1, team2
            FROM worldcup_matches
            WHERE score_ft_team1 IS NULL
              AND team1 NOT LIKE 'W%%' AND team1 NOT LIKE 'L%%'
              AND team2 NOT LIKE 'W%%' AND team2 NOT LIKE 'L%%'
        """)
        return cur.fetchall()


def _h2h(conn, team_ids, team1, team2):
    def find_id(name):
        return next((v for k, v in team_ids.items() if pair_matches(name, name, k, k)), None)

    id1 = find_id(team1)
    id2 = find_id(team2)
    if not id1 or not id2:
        return 0

    data = _get(f"/teams/{id1}/matches", status="FINISHED", limit=100)
    rows = []
    for match in data.get("matches", []):
        home = (match.get("homeTeam") or {}).get("name")
        away = (match.get("awayTeam") or {}).get("name")
        if not pair_matches(team1, team2, home, away):
            continue
        score = (match.get("score") or {}).get("fullTime") or {}
        hs, as_ = score.get("home"), score.get("away")
        if hs is None or as_ is None:
            continue
        winner = None
        if hs > as_:
            winner = home
        elif as_ > hs:
            winner = away
        rows.append((parse_date(match.get("utcDate")), match.get("stage"), f"{home} {hs}-{as_} {away}", winner, match))

    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM h2h_history
            WHERE source = %s
              AND ((team1 = %s AND team2 = %s) OR (team1 = %s AND team2 = %s))
        """, ("football-data.org", team1, team2, team2, team1))
        for date, stage, score_summary, winner, raw in rows:
            cur.execute("""
                INSERT INTO h2h_history (team1, team2, year, round, score_summary, winner, notes, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (team1, team2, date.year if date else 0, stage, score_summary, winner, "auto from football-data.org team matches", "football-data.org"))
    return len(rows)


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        if not os.environ.get("FOOTBALL_DATA_TOKEN"):
            db.log_collection(conn, "football-data.org", "matches", "WC", "partial", "missing FOOTBALL_DATA_TOKEN")
            print("Skipping football-data.org: FOOTBALL_DATA_TOKEN is not set")
            return

        comp = os.environ.get("FOOTBALL_DATA_COMPETITION", "WC")
        data = _get(f"/competitions/{comp}/matches")
        matches = data.get("matches", [])
        for match in matches:
            _store_match(conn, match)

        team_ids = _competition_teams()
        h2h_count = 0
        for team1, team2 in _upcoming_pairs(conn):
            h2h_count += _h2h(conn, team_ids, team1, team2)

        conn.commit()
        db.log_collection(conn, "football-data.org", "matches", comp, "success", f"{len(matches)} matches, {h2h_count} h2h rows")
        print(f"football-data.org stored {len(matches)} matches and {h2h_count} h2h rows")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "football-data.org", "matches", os.environ.get("FOOTBALL_DATA_COMPETITION", "WC"), "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
