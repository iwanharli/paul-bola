"""
Derived context collector.

Builds non-official but useful frontend coverage tables:
  - projected_team_lineups from ESPN starter frequency + FIFA squad fallback
  - team_availability_coverage from FIFA squad SpecialStatus presence
  - team_player_attack_summary from FIFA shot events

No network calls. Safe to run every orchestrator cycle.
"""
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

import db

TEAM_ALIASES = {
    "United States": "USA",
    "USA": "United States",
    "Türkiye": "Turkey",
    "Turkey": "Türkiye",
    "Czechia": "Czech Republic",
    "Czech Republic": "Czechia",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Bosnia & Herzegovina": "Bosnia-Herzegovina",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Cabo Verde": "Cape Verde",
    "DR Congo": "Congo DR",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Ivory Coast": "Côte d'Ivoire",
}


def canonical_team(name):
    return TEAM_ALIASES.get(name, name)


def _clear(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE projected_team_lineups")
        cur.execute("TRUNCATE team_availability_coverage")
        cur.execute("TRUNCATE team_player_attack_summary")


def _projected_lineups(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT r.team_name, r.player_name, r.jersey,
                   count(*) AS appearances,
                   count(*) FILTER (WHERE r.starter) AS starts,
                   max(r.espn_event_id) AS last_event_id
            FROM espn_match_rosters r
            GROUP BY r.team_name, r.player_name, r.jersey
        """)
        rows = cur.fetchall()

    by_team = defaultdict(list)
    for team, player, jersey, appearances, starts, last_event_id in rows:
        if not player:
            continue
        by_team[canonical_team(team)].append({
            "player_name": player,
            "shirt_number": int(jersey) if str(jersey or "").isdigit() else None,
            "appearances": int(appearances or 0),
            "starts": int(starts or 0),
            "last_event_id": last_event_id,
            "source_team": team,
        })

    for team, players in by_team.items():
        players.sort(key=lambda row: (row["starts"], row["appearances"]), reverse=True)
        selected = players[:11] if len(players) >= 11 else players
        for row in selected:
            confidence = row["starts"] / row["appearances"] if row["appearances"] else 0
            db.upsert_composite(conn, "projected_team_lineups", {
                "team_name": team,
                "player_name": row["player_name"],
                "shirt_number": row["shirt_number"],
                "position": None,
                "starts": row["starts"],
                "appearances": row["appearances"],
                "confidence": round(float(confidence), 3),
                "source": "derived:espn_match_rosters",
                "raw": row,
            }, ["team_name", "player_name"])

    # If a team still has no projection, use a conservative FIFA squad fallback
    # sorted by position and shirt number. It is squad coverage, not official XI.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT team
            FROM (
                SELECT team1 AS team FROM worldcup_matches
                UNION SELECT team2 AS team FROM worldcup_matches
            ) t
            WHERE team IS NOT NULL AND team NOT LIKE 'W%%' AND team NOT LIKE 'L%%'
            ORDER BY team
        """)
        teams = [row[0] for row in cur.fetchall()]
        cur.execute("""
            SELECT fifa_team_id, player_name, shirt_number, position, raw
            FROM fifa_squads
            ORDER BY fifa_team_id, position NULLS LAST, shirt_number NULLS LAST, player_name
        """)
        squads = cur.fetchall()

    # Build a loose team-id to team-name map from existing projected rows and
    # FIFA squad collection scopes are not persisted, so fallback only applies
    # when ESPN produced no rows via aliases. This keeps the fallback harmless.
    existing = set(by_team)
    squad_by_name = defaultdict(list)
    for team in teams:
        if team in existing:
            continue
        # Use player names from any squad matching this team in player_crosswalk.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.player_name, s.shirt_number, s.position, s.raw
                FROM fifa_squads s
                JOIN player_crosswalk c ON c.fifa_player_id = s.fifa_player_id
                WHERE c.espn_team_name = %s OR c.espn_team_name = %s
                ORDER BY s.position NULLS LAST, s.shirt_number NULLS LAST, s.player_name
                LIMIT 11
            """, (team, TEAM_ALIASES.get(team, team)))
            squad_by_name[team] = cur.fetchall()

    for team, rows in squad_by_name.items():
        for player_name, shirt_number, position, raw in rows:
            db.upsert_composite(conn, "projected_team_lineups", {
                "team_name": team,
                "player_name": player_name.title(),
                "shirt_number": shirt_number,
                "position": position,
                "starts": 0,
                "appearances": 0,
                "confidence": 0,
                "source": "fallback:fifa_squads",
                "raw": raw,
            }, ["team_name", "player_name"])


def _availability_coverage(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(c.espn_team_name, fs.fifa_team_id::text) AS team_name,
                   count(*) AS player_count,
                   count(*) FILTER (WHERE fs.raw ? 'SpecialStatus' AND fs.raw->'SpecialStatus' IS NOT NULL) AS special_count
            FROM fifa_squads fs
            LEFT JOIN player_crosswalk c ON c.fifa_player_id = fs.fifa_player_id
            GROUP BY COALESCE(c.espn_team_name, fs.fifa_team_id::text)
        """)
        rows = cur.fetchall()

    merged = defaultdict(lambda: {"player_count": 0, "special_status_count": 0, "source_rows": []})
    for team, player_count, special_count in rows:
        team = canonical_team(team)
        merged[team]["player_count"] += int(player_count or 0)
        merged[team]["special_status_count"] += int(special_count or 0)
        merged[team]["source_rows"].append({"team": team, "player_count": int(player_count or 0), "special_count": int(special_count or 0)})

    for team, row in merged.items():
        db.upsert(conn, "team_availability_coverage", {
            "team_name": team,
            "player_count": row["player_count"],
            "special_status_count": row["special_status_count"],
            "source": "derived:fifa_squads.SpecialStatus",
            "raw": row,
        }, "team_name")


def _attack_summary(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(c.espn_team_name, s.fifa_team_id::text) AS team_name,
                   s.player_name,
                   count(e.event_id) AS shots,
                   count(e.event_id) FILTER (WHERE e.is_goal) AS goals
            FROM fifa_shot_events e
            JOIN fifa_squads s ON s.fifa_player_id = e.player_id
            LEFT JOIN player_crosswalk c ON c.fifa_player_id = s.fifa_player_id
            GROUP BY COALESCE(c.espn_team_name, s.fifa_team_id::text), s.player_name
        """)
        rows = cur.fetchall()

    for team, player, shots, goals in rows:
        db.upsert_composite(conn, "team_player_attack_summary", {
            "team_name": canonical_team(team),
            "player_name": player.title(),
            "goals": int(goals or 0),
            "shots": int(shots or 0),
            "source": "derived:fifa_shot_events",
            "raw": {"source_team": team},
        }, ["team_name", "player_name"])


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        _clear(conn)
        _projected_lineups(conn)
        _availability_coverage(conn)
        _attack_summary(conn)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM projected_team_lineups")
            lineups = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM team_availability_coverage")
            coverage = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM team_player_attack_summary")
            attack = cur.fetchone()[0]
        db.log_collection(conn, "internal", "derived_context", "lineups+availability+attack", "success",
                          f"{lineups} lineup rows, {coverage} availability coverage rows, {attack} attack rows")
        print(f"Derived context: {lineups} lineup rows, {coverage} availability rows, {attack} attack rows")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "internal", "derived_context", "lineups+availability+attack", "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
