"""
FIFA match-centre context collector -> fifa_match_index + fifa_match_lineups.

No registration/API key. Uses FIFA public calendar and live match endpoints.
For future matches, lineups may be squad-only until official team sheets are
published. Raw payload is stored so fields can be audited later.
"""
import requests
from dotenv import load_dotenv

load_dotenv()

import db
from fifa_officials_collect import BASE, COMPETITION_ID, HEADERS, SEASON_ID, get_calendar_matches, store_match_index
from config import COMPETITION


def _localized(value):
    if isinstance(value, list) and value:
        return value[0].get("Description") if isinstance(value[0], dict) else None
    if isinstance(value, dict):
        return value.get("Description")
    return value


def _team_name(match_team):
    return _localized((match_team or {}).get("TeamName")) or (match_team or {}).get("Name")


def _both_teams_ready(match):
    """True only if both teams are resolved (real IdTeam). Guards against
    unplayed knockout matches still carrying W../L.. placeholders."""
    for side in ("Home", "Away"):
        team = match.get(side)
        if not team or not team.get("IdTeam"):
            return False
    return True


def _player_status(player):
    for key in ("Status", "SpecialStatus", "LineupStatus", "PlayerStatus"):
        value = player.get(key)
        if value:
            return _localized(value)
    return None


def _starter(player):
    for key in ("Starter", "IsStarter", "Starting", "IsStarting"):
        if key in player:
            return bool(player.get(key))
    # FIFA lineups often expose a Type/Status only after confirmation; leave
    # unknown as NULL rather than inventing starter/substitute.
    return None


def _captain(player):
    for key in ("Captain", "IsCaptain"):
        if key in player:
            return bool(player.get(key))
    return None


def collect_match_lineups(conn, match):
    match_id = int(match["IdMatch"])
    id_stage = match.get("IdStage")
    if not id_stage:
        return 0

    resp = requests.get(
        f"{BASE}/live/football/{COMPETITION_ID}/{SEASON_ID}/{id_stage}/{match_id}",
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json() or {}

    count = 0
    for side in ("HomeTeam", "AwayTeam"):
        team = data.get(side) or {}
        team_name = _team_name(team)
        team_id = team.get("IdTeam")
        for player in team.get("Players", []) or []:
            player_id = player.get("IdPlayer")
            player_name = _localized(player.get("PlayerName"))
            if not player_id or not player_name:
                continue
            db.upsert_composite(conn, "fifa_match_lineups", {
                "competition": COMPETITION,
                "fifa_match_id": match_id,
                "fifa_team_id": int(team_id) if team_id else None,
                "team_name": team_name,
                "fifa_player_id": int(player_id),
                "player_name": player_name,
                "shirt_number": player.get("ShirtNumber"),
                "position": player.get("Position"),
                "starter": _starter(player),
                "captain": _captain(player),
                "status": _player_status(player),
                "raw": player,
            }, ["fifa_match_id", "fifa_player_id"])
            count += 1
    return count


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        matches = get_calendar_matches()
        lineups = 0
        indexed = 0
        for match in matches:
            store_match_index(conn, match)
            indexed += 1
            # Pull lineups for upcoming/recent knockout matches only; the live
            # endpoint is heavier than calendar and not needed for all 104 rows.
            stage_name = _localized(match.get("StageName")) or _localized(match.get("GroupName")) or ""
            status = str(match.get("MatchStatus") or match.get("Status") or "")
            wants_lineup = (
                any(token in stage_name.lower() for token in ("semi", "final", "third"))
                or status.lower() not in {"finished", "fulltime"}
            )
            # Skip matches whose teams aren't resolved yet (e.g. the final /
            # bronze final still showing "W102"/"L102" placeholders -- FIFA
            # returns Away=None for these). Pulling them was retrying and
            # logging a benign NoneType error every 15-min cron cycle.
            if wants_lineup and _both_teams_ready(match):
                try:
                    lineups += collect_match_lineups(conn, match)
                except Exception as exc:  # noqa: BLE001
                    db.log_collection(conn, "fifa", "match_lineups", f"match:{match.get('IdMatch')}", "error", str(exc))
        conn.commit()
        db.log_collection(conn, "fifa", "match_context", "calendar+lineups", "success", f"{indexed} indexed, {lineups} lineup rows")
        print(f"FIFA match context: {indexed} indexed, {lineups} lineup rows")
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
