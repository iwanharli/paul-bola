"""
StatsBomb Open Data collector -> db_boforecasting.

Focuses on club leagues (per user decision) since StatsBomb open data does not
yet include the current World Cup, and current-season Premier League data is
not in the free open-data tier (only 2015/2016 and 2003/2004 are available).

Usage:
    python statsbomb_collect.py list                      # show all open-data competitions/seasons
    python statsbomb_collect.py competition <comp_id> <season_id>
    python statsbomb_collect.py latest <comp_id>          # auto-pick most recent season for a competition

xG per team per match is computed by summing statsbomb_xg across shot events,
since StatsBomb's open match-level summary doesn't expose a ready-made xG field.
"""
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="statsbombpy")

from dotenv import load_dotenv

load_dotenv()

from statsbombpy import sb
import db

SCHEMA_PATH = "../db/schema.sql"


def _team_row(team_id: int, team_name: str) -> dict:
    return {"id": team_id, "name": team_name, "country": None, "raw": {"name": team_name}}


def _match_row(match: dict) -> dict:
    return {
        "id": match["match_id"],
        "competition_id": match["competition_id"],
        "season_id": match["season_id"],
        "stage": match.get("competition_stage"),
        "matchday": match.get("match_week"),
        "kickoff_utc": match.get("match_date"),
        "status": "finished",
        "home_team_id": match["home_team_id"],
        "away_team_id": match["away_team_id"],
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "venue": match.get("stadium"),
        "referee": match.get("referee"),
        "raw": {k: str(v) for k, v in match.items()},
    }


def list_competitions():
    comps = sb.competitions()
    print(comps[["competition_id", "season_id", "country_name", "competition_name", "season_name"]].to_string())


def latest_season_id(competition_id: int) -> int:
    comps = sb.competitions()
    rows = comps[comps["competition_id"] == competition_id]
    if rows.empty:
        raise ValueError(f"No competition with id {competition_id}")
    # season_name sorts lexically close enough to chronological for "YYYY" and "YYYY/YYYY" formats
    rows = rows.sort_values("season_name", ascending=False)
    return int(rows.iloc[0]["season_id"])


def collect_competition(conn, competition_id: int, season_id: int):
    comps = sb.competitions()
    comp_row = comps[(comps["competition_id"] == competition_id) & (comps["season_id"] == season_id)]
    if comp_row.empty:
        raise ValueError(f"No such competition/season: {competition_id}/{season_id}")
    comp_row = comp_row.iloc[0]

    db.upsert(conn, "competitions", {
        "id": competition_id,
        "name": comp_row["competition_name"],
        "country": comp_row["country_name"],
        "type": "club_league",
        "raw": {"season_name": comp_row["season_name"]},
    })
    conn.commit()

    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    print(f"Found {len(matches)} matches for {comp_row['competition_name']} {comp_row['season_name']}")

    seen_teams = set()
    for _, match in matches.iterrows():
        match = match.to_dict()
        match["competition_id"] = competition_id
        match["season_id"] = season_id

        for team_key in ("home_team_id", "away_team_id"):
            team_id = match[team_key]
            team_name = match[team_key.replace("_id", "")]
            if team_id not in seen_teams:
                db.upsert(conn, "teams", _team_row(team_id, team_name))
                seen_teams.add(team_id)

        db.upsert(conn, "matches", _match_row(match))
        conn.commit()

        match_id = match["match_id"]
        try:
            events = sb.events(match_id=match_id)
        except Exception as exc:  # noqa: BLE001
            db.log_collection(conn, "statsbomb", "events", f"match:{match_id}", "error", str(exc))
            continue

        shots = events[events["type"] == "Shot"]
        for team_key, team_id_key in (("home_team", "home_team_id"), ("away_team", "away_team_id")):
            team_name = match[team_key]
            team_id = match[team_id_key]
            team_shots = shots[shots["team"] == team_name]
            xg_sum = team_shots["shot_statsbomb_xg"].sum() if "shot_statsbomb_xg" in team_shots.columns else None
            shots_on_target = None
            if "shot_outcome" in team_shots.columns:
                shots_on_target = int((team_shots["shot_outcome"] == "Goal").sum() +
                                       (team_shots["shot_outcome"] == "Saved").sum())

            db.upsert_composite(conn, "match_stats", {
                "match_id": match_id,
                "team_id": team_id,
                "is_home": team_key == "home_team",
                "xg": round(float(xg_sum), 4) if xg_sum is not None else None,
                "xg_first_half": None,
                "xg_second_half": None,
                "shots": len(team_shots),
                "shots_on_target": shots_on_target,
                "possession_pct": None,
                "passes": None,
                "corners": None,
                "fouls": None,
                "yellow_cards": None,
                "red_cards": None,
                "raw": {},
            }, ["match_id", "team_id"])
        conn.commit()

    db.log_collection(conn, "statsbomb", "competition", f"competition:{competition_id}/season:{season_id}",
                       "success", f"{len(matches)} matches")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        list_competitions()
        return

    conn = db.connect()
    try:
        if cmd == "latest":
            competition_id = int(sys.argv[2])
            season_id = latest_season_id(competition_id)
            print(f"Latest season for competition {competition_id} is {season_id}")
            collect_competition(conn, competition_id, season_id)
        elif cmd == "competition":
            competition_id = int(sys.argv[2])
            season_id = int(sys.argv[3])
            collect_competition(conn, competition_id, season_id)
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
