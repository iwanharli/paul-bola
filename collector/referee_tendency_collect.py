"""
Compute real referee card tendency from data we ALREADY collected --
fifa_match_officials (referee per match) + espn_match_team_stats (cards per
team per match) -- instead of the single manually-cross-referenced n=2
sample built earlier for Ismail Elfath alone.

No new external source needed: this just joins two datasets already in the
DB. The only missing piece is a FIFA-match <-> ESPN-event crosswalk, which
doesn't exist as a stored table, so this rebuilds it by team-name+date
matching (same normalized-name approach used in build_player_crosswalk.py)
against a fresh ESPN scoreboard pull (cheap: ~31 date queries).

Usage:
    python referee_tendency_collect.py
"""
import re
import unicodedata

import requests
from dotenv import load_dotenv

load_dotenv()

import db
import espn_collect


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def build_espn_crosswalk(conn):
    """date -> {frozenset({home,away}): espn_event_id}"""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT match_date FROM worldcup_matches WHERE score_ft_team1 IS NOT NULL")
    dates = [r[0] for r in cur.fetchall()]

    crosswalk = {}
    for d in dates:
        date_str = d.strftime("%Y%m%d")
        try:
            events = espn_collect.get_scoreboard(date_str)
        except Exception:  # noqa: BLE001
            continue
        for e in events:
            name = e.get("name", "")
            if " at " not in name:
                continue
            away, home = name.split(" at ", 1)
            key = frozenset([norm(home), norm(away)])
            crosswalk[key] = e["id"]
    return crosswalk


def collect():
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT fmo.name, fmi.home_team, fmi.away_team, fmi.match_date
            FROM fifa_match_officials fmo
            JOIN fifa_match_index fmi ON fmi.fifa_match_id = fmo.fifa_match_id
            WHERE fmo.role = 'Referee' AND fmi.home_team IS NOT NULL
        """)
        referee_matches = cur.fetchall()

        espn_crosswalk = build_espn_crosswalk(conn)
        print(f"Built ESPN crosswalk: {len(espn_crosswalk)} matches")

        cur.execute("SELECT espn_event_id, team_name, yellow_cards, red_cards FROM espn_match_team_stats")
        card_rows = cur.fetchall()
        cards_by_event = {}
        for eid, team, yc, rc in card_rows:
            cards_by_event.setdefault(eid, []).append((yc or 0, rc or 0))

        per_ref = {}  # name -> list of (total_yellow, total_red) per match
        matched = 0
        for name, home, away, date in referee_matches:
            key = frozenset([norm(home), norm(away)])
            eid = espn_crosswalk.get(key)
            if not eid:
                continue
            cards = cards_by_event.get(int(eid))
            if not cards or len(cards) != 2:
                continue
            total_yellow = sum(c[0] for c in cards)
            total_red = sum(c[1] for c in cards)
            per_ref.setdefault(name, []).append((total_yellow, total_red))
            matched += 1

        print(f"Matched {matched}/{len(referee_matches)} referee-match rows to card data")

        cur.execute("TRUNCATE referee_tendency RESTART IDENTITY")
        for name, samples in per_ref.items():
            n = len(samples)
            avg_yellow = sum(s[0] for s in samples) / n
            avg_red = sum(s[1] for s in samples) / n
            cur.execute("""
                INSERT INTO referee_tendency
                    (referee_name, matches_sampled, avg_yellow_per_match, avg_red_per_match, notes, source)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, n, round(avg_yellow, 2), round(avg_red, 2),
                  f"Computed from {n} matches this tournament (FIFA officials x ESPN cards join).",
                  "derived:fifa_match_officials+espn_match_team_stats"))
        conn.commit()

        db.log_collection(conn, "internal", "referee_tendency", "all_referees", "success",
                           f"{len(per_ref)} referees, {matched} matches")
        print(f"Stored tendency for {len(per_ref)} referees")

        cur.execute("SELECT referee_name, matches_sampled, avg_yellow_per_match, avg_red_per_match "
                     "FROM referee_tendency ORDER BY matches_sampled DESC LIMIT 10")
        for row in cur.fetchall():
            print(" ", row)
    finally:
        conn.close()


if __name__ == "__main__":
    collect()
