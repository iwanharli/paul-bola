"""
The Odds API collector -> match_odds_snapshot.

Requires registration/API key:
    THE_ODDS_API_KEY=...

Optional env:
    THE_ODDS_API_SPORT_KEYS=soccer_fifa_world_cup,soccer_international
    THE_ODDS_API_REGIONS=us,uk,eu

It writes the latest h2h/1X2 bookmaker prices into match_odds_snapshot for
upcoming World Cup matches. If the key is missing, it logs a skipped run.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

import db
from source_utils import american_price, pair_matches, parse_date, team_names_match

BASE = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT_KEYS = [
    "soccer_fifa_world_cup",
    "soccer_international",
    "soccer_conmebol_copa_america",
]


def _current_matches(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT match_date, team1, team2
            FROM worldcup_matches
            WHERE score_ft_team1 IS NULL
              AND match_date >= CURRENT_DATE - INTERVAL '1 day'
            ORDER BY match_date, match_num
        """)
        return cur.fetchall()


def _configured_sport_keys(api_key):
    configured = [s.strip() for s in os.environ.get("THE_ODDS_API_SPORT_KEYS", "").split(",") if s.strip()]
    if configured:
        return configured
    try:
        resp = requests.get(f"{BASE}/sports", params={"apiKey": api_key}, timeout=30)
        resp.raise_for_status()
        keys = [row["key"] for row in resp.json() if row.get("active") and row.get("key", "").startswith("soccer")]
        ranked = [key for key in keys if any(word in key for word in ("fifa", "world", "international"))]
        return ranked or DEFAULT_SPORT_KEYS
    except Exception:  # noqa: BLE001
        return DEFAULT_SPORT_KEYS


def _outcome_map(outcomes):
    out = {}
    for outcome in outcomes or []:
        name = outcome.get("name") or ""
        key = "draw" if name.lower() == "draw" else name
        out[key] = outcome.get("price")
    return out


def _write_event(conn, match, event, sport_key):
    match_date, team1, team2 = match
    home = event.get("home_team")
    away = event.get("away_team")
    if not pair_matches(team1, team2, home, away):
        return 0

    count = 0
    commence_time = event.get("commence_time")
    event_date = parse_date(commence_time) or match_date
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = _outcome_map(market.get("outcomes"))
            team1_price = next((price for name, price in outcomes.items() if name != "draw" and team_names_match(team1, name)), None)
            team2_price = next((price for name, price in outcomes.items() if name != "draw" and team_names_match(team2, name)), None)

            # Refresh the latest snapshot per bookmaker/source to avoid
            # unbounded duplicates during 15-min cron runs.
            bookmaker_name = bookmaker.get("title") or bookmaker.get("key") or "unknown"
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM match_odds_snapshot
                    WHERE source = %s AND team1 = %s AND team2 = %s
                      AND match_date = %s AND bookmaker = %s AND market = %s
                """, ("the-odds-api", team1, team2, event_date, bookmaker_name, "90min_moneyline"))

            db.upsert(conn, "match_odds_snapshot", {
                "team1": team1,
                "team2": team2,
                "match_date": event_date,
                "bookmaker": bookmaker_name,
                "market": "90min_moneyline",
                "team1_odds": american_price(team1_price),
                "draw_odds": american_price(outcomes.get("draw")),
                "team2_odds": american_price(team2_price),
                "notes": f"h2h market from {sport_key}",
                "source": "the-odds-api",
                "source_event_id": event.get("id"),
                "sport_key": sport_key,
                "commence_time": commence_time,
                "raw": {"event": event, "bookmaker": bookmaker, "market": market},
            }, "id")
            count += 1
    return count


def collect(conn=None):
    api_key = os.environ.get("THE_ODDS_API_KEY")
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        if not api_key:
            db.log_collection(conn, "the-odds-api", "odds", "all", "partial", "missing THE_ODDS_API_KEY")
            print("Skipping The Odds API: THE_ODDS_API_KEY is not set")
            return

        matches = _current_matches(conn)
        if not matches:
            db.log_collection(conn, "the-odds-api", "odds", "all", "success", "no upcoming matches")
            return

        total = 0
        regions = os.environ.get("THE_ODDS_API_REGIONS", "us,uk,eu")
        for sport_key in _configured_sport_keys(api_key):
            resp = requests.get(
                f"{BASE}/sports/{sport_key}/odds",
                params={
                    "apiKey": api_key,
                    "regions": regions,
                    "markets": "h2h",
                    "oddsFormat": "american",
                },
                timeout=30,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            for event in resp.json():
                for match in matches:
                    total += _write_event(conn, match, event, sport_key)
            conn.commit()

        db.log_collection(conn, "the-odds-api", "odds", "upcoming_worldcup", "success", f"{total} bookmaker snapshots")
        print(f"The Odds API stored {total} bookmaker snapshots")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "the-odds-api", "odds", "upcoming_worldcup", "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
