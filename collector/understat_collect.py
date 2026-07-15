"""
Understat collector -> db_boforecasting.

Covers current-season (2025/26) xG for the Big 5 European leagues + RFPL.
No API key needed. Used for club-level attack/defense base rates on key
players (e.g. Bellingham at Real Madrid is in La Liga -- not covered here,
Understat has no La_Liga endpoint under this name; recheck `LEAGUES` below
if La Liga support changes).

Usage:
    python understat_collect.py <league> <season>
    python understat_collect.py EPL 2025
    python understat_collect.py all 2025      # loop all known leagues
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from understatapi import UnderstatClient
import db

LEAGUES = ["EPL", "La_Liga", "Bundesliga", "Serie_A", "Ligue_1", "RFPL"]


def collect_league(client: UnderstatClient, conn, league: str, season: str):
    matches = client.league(league=league).get_match_data(season=season)
    finished = [m for m in matches if m.get("isResult")]
    print(f"{league} {season}: {len(finished)}/{len(matches)} matches played")

    for m in finished:
        db.upsert(conn, "understat_matches", {
            "id": int(m["id"]),
            "league": league,
            "season": season,
            "kickoff_utc": m.get("datetime"),
            "home_team": m["h"]["title"],
            "away_team": m["a"]["title"],
            "home_goals": int(m["goals"]["h"]),
            "away_goals": int(m["goals"]["a"]),
            "home_xg": float(m["xG"]["h"]),
            "away_xg": float(m["xG"]["a"]),
            "forecast_win": float(m["forecast"]["w"]) if m.get("forecast") else None,
            "forecast_draw": float(m["forecast"]["d"]) if m.get("forecast") else None,
            "forecast_loss": float(m["forecast"]["l"]) if m.get("forecast") else None,
            "raw": m,
        })
    conn.commit()
    db.log_collection(conn, "understat", "league_matches", f"{league}/{season}", "success",
                       f"{len(finished)} matches")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    league_arg, season = sys.argv[1], sys.argv[2]
    client = UnderstatClient()
    conn = db.connect()
    try:
        leagues = LEAGUES if league_arg == "all" else [league_arg]
        for league in leagues:
            try:
                collect_league(client, conn, league, season)
            except Exception as exc:  # noqa: BLE001
                db.log_collection(conn, "understat", "league_matches", f"{league}/{season}", "error", str(exc))
                print(f"ERROR {league}: {exc}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
