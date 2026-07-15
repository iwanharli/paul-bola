"""
Build player_crosswalk by normalized-name matching across fifa_squads,
espn_match_rosters, and asa_player_season_xg. No shared id exists across
these three sources, so this is the best-effort link -- rows are tagged with
match_method so low-confidence matches can be audited later.

Usage:
    python build_player_crosswalk.py
"""
import re
import unicodedata

from dotenv import load_dotenv

load_dotenv()

import db


def normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower().strip()
    ascii_name = re.sub(r"[^a-z\s]", "", ascii_name)
    ascii_name = re.sub(r"\s+", " ", ascii_name)
    return ascii_name


def build():
    conn = db.connect()
    try:
        cur = conn.cursor()

        cur.execute("SELECT fifa_player_id, fifa_team_id, player_name FROM fifa_squads")
        fifa_rows = cur.fetchall()

        cur.execute("SELECT DISTINCT espn_athlete_id, team_name, player_name FROM espn_match_rosters")
        espn_rows = cur.fetchall()
        espn_by_norm = {}
        for eid, team, name in espn_rows:
            espn_by_norm.setdefault(normalize(name), []).append((eid, team, name))

        cur.execute("SELECT DISTINCT player_id, player_name FROM asa_player_season_xg")
        asa_rows = cur.fetchall()
        asa_by_norm = {}
        for pid, name in asa_rows:
            asa_by_norm.setdefault(normalize(name), []).append((pid, name))

        cur.execute("TRUNCATE player_crosswalk")

        matched_espn = 0
        matched_asa = 0
        for fifa_id, fifa_team_id, fifa_name in fifa_rows:
            norm = normalize(fifa_name)
            espn_matches = espn_by_norm.get(norm, [])
            asa_matches = asa_by_norm.get(norm, [])

            espn_id, espn_team = (espn_matches[0][0], espn_matches[0][1]) if len(espn_matches) == 1 else (None, None)
            asa_id = asa_matches[0][0] if len(asa_matches) == 1 else None

            if espn_id:
                matched_espn += 1
            if asa_id:
                matched_asa += 1

            method = "normalized_name_exact" if (espn_id or asa_id) else "unmatched"
            cur.execute("""
                INSERT INTO player_crosswalk
                    (canonical_name, fifa_player_id, fifa_team_id, espn_athlete_id,
                     espn_team_name, asa_player_id, match_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (fifa_name, fifa_id, fifa_team_id, espn_id, espn_team, asa_id, method))

        conn.commit()
        print(f"Built crosswalk for {len(fifa_rows)} FIFA squad players")
        print(f"  matched to ESPN: {matched_espn}")
        print(f"  matched to ASA (MLS): {matched_asa}")

        db.log_collection(conn, "internal", "player_crosswalk", "fifa_squads",
                           "success", f"{matched_espn} espn matches, {matched_asa} asa matches")
    finally:
        conn.close()


if __name__ == "__main__":
    build()
