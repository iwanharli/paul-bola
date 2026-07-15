"""
Collector entrypoint for bola-forecasting.

Usage:
    python collect.py init                              # create db + schema only
    python collect.py competition <competition_id>       # pull matches + stats for one competition (all seasons found)
    python collect.py competition <competition_id> <season_id>
    python collect.py team-players <team_id>              # pull squad roster for base-rate/player priors

Scope decided with the user: World Cup competition first, then club leagues
for key players' base attack/defense rates. Find competition_ids via:
    python -c "from statsapi_client import StatsAPIClient; c = StatsAPIClient();
    [print(x['id'], x['name'], x.get('country')) for x in c.list_competitions()]"
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from statsapi_client import StatsAPIClient
import db

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")


def init_db():
    db.ensure_database()
    conn = db.connect()
    try:
        db.apply_schema(conn, SCHEMA_PATH)
        print("Schema applied.")
    finally:
        conn.close()


def _team_row(team: dict) -> dict:
    return {
        "id": team["id"],
        "name": team.get("name"),
        "country": team.get("country"),
        "raw": team,
    }


def _match_row(match: dict) -> dict:
    return {
        "id": match["id"],
        "competition_id": (match.get("competition") or {}).get("id"),
        "season_id": (match.get("season") or {}).get("id"),
        "stage": match.get("stage"),
        "matchday": match.get("matchday"),
        "kickoff_utc": match.get("kickoff") or match.get("utc_kickoff") or match.get("date"),
        "status": match.get("status"),
        "home_team_id": (match.get("home_team") or {}).get("id"),
        "away_team_id": (match.get("away_team") or {}).get("id"),
        "home_score": (match.get("score") or {}).get("home"),
        "away_score": (match.get("score") or {}).get("away"),
        "venue": match.get("venue"),
        "referee": match.get("referee"),
        "raw": match,
    }


def collect_competition(client: StatsAPIClient, conn, competition_id: int, season_id: int | None = None):
    comp = client.get_competition(competition_id).get("data", {})
    db.upsert(conn, "competitions", {
        "id": comp.get("id", competition_id),
        "name": comp.get("name"),
        "country": comp.get("country"),
        "type": comp.get("type"),
        "raw": comp,
    })
    conn.commit()

    matches = list(client.list_matches(competition_id=competition_id))
    if season_id:
        matches = [m for m in matches if (m.get("season") or {}).get("id") == season_id]

    print(f"Found {len(matches)} matches for competition {competition_id}")

    seen_teams = set()
    for match in matches:
        for side in ("home_team", "away_team"):
            team = match.get(side)
            if team and team.get("id") not in seen_teams:
                db.upsert(conn, "teams", _team_row(team))
                seen_teams.add(team["id"])

        db.upsert(conn, "matches", _match_row(match))
        conn.commit()

        match_id = match["id"]
        try:
            stats = client.get_match_stats(match_id)
        except Exception as exc:  # noqa: BLE001
            db.log_collection(conn, "thestatsapi", "match_stats", f"match:{match_id}", "error", str(exc))
            continue

        for side_key, is_home in (("home", True), ("away", False)):
            side_stats = stats.get(side_key) or {}
            team_id = (match.get(f"{side_key}_team") or {}).get("id")
            if not team_id:
                continue
            db.upsert_composite(conn, "match_stats", {
                "match_id": match_id,
                "team_id": team_id,
                "is_home": is_home,
                "xg": side_stats.get("xg"),
                "xg_first_half": side_stats.get("xg_first_half"),
                "xg_second_half": side_stats.get("xg_second_half"),
                "shots": side_stats.get("shots"),
                "shots_on_target": side_stats.get("shots_on_target"),
                "possession_pct": side_stats.get("possession"),
                "passes": side_stats.get("passes"),
                "corners": side_stats.get("corners"),
                "fouls": side_stats.get("fouls"),
                "yellow_cards": side_stats.get("yellow_cards"),
                "red_cards": side_stats.get("red_cards"),
                "raw": side_stats,
            }, ["match_id", "team_id"])
        conn.commit()

    db.log_collection(conn, "thestatsapi", "competition", f"competition:{competition_id}", "success",
                       f"{len(matches)} matches")


def collect_team_players(client: StatsAPIClient, conn, team_id: int):
    team = client.get_team(team_id)
    db.upsert(conn, "teams", _team_row(team))
    conn.commit()

    players = client.get_team_players(team_id)
    for p in players:
        db.upsert(conn, "players", {
            "id": p["id"],
            "name": p.get("name"),
            "team_id": team_id,
            "position": p.get("position"),
            "raw": p,
        })
    conn.commit()
    print(f"Collected {len(players)} players for team {team_id}")
    db.log_collection(conn, "thestatsapi", "team_players", f"team:{team_id}", "success", f"{len(players)} players")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init_db()
        return

    client = StatsAPIClient()
    conn = db.connect()
    try:
        if cmd == "competition":
            competition_id = int(sys.argv[2])
            season_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
            collect_competition(client, conn, competition_id, season_id)
        elif cmd == "team-players":
            team_id = int(sys.argv[2])
            collect_team_players(client, conn, team_id)
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
