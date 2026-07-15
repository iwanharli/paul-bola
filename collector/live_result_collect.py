"""
Fast final-result fallback -> worldcup_matches.

Our primary score source (openfootball) is hand-maintained ~daily, so a match
can finish hours before its result lands in worldcup_matches. ESPN's public
scoreboard reports the final result within minutes. This collector fills
score_ft from ESPN for matches ESPN marks COMPLETED but that still have a
null score in our DB -- so the site reflects reality promptly. openfootball
later refines the ft/et/pens breakdown.

STRICT guard: only writes matches ESPN reports as completed (state == "post",
completed == True). A live/in-progress score (e.g. 1-0 at 74') is NEVER
written as a final result.

Usage:
    python live_result_collect.py <YYYYMMDD> [<YYYYMMDD> ...]
    python live_result_collect.py               # defaults to today + yesterday (UTC)
"""
import datetime
import re
import sys
import unicodedata

import requests
from dotenv import load_dotenv

load_dotenv()

import db

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def get_scoreboard(date_str):
    r = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("events", [])


def collect(conn=None, dates=None):
    own = conn is None
    if own:
        conn = db.connect()
    try:
        if not dates:
            today = datetime.datetime.utcnow().date()
            dates = [today.strftime("%Y%m%d"),
                     (today - datetime.timedelta(days=1)).strftime("%Y%m%d")]

        # map our finished-or-pending matches by normalized team pair
        cur = conn.cursor()
        cur.execute("""
            SELECT match_num, team1, team2, score_ft_team1
            FROM worldcup_matches
        """)
        by_pair = {}
        for match_num, t1, t2, ft1 in cur.fetchall():
            by_pair[frozenset([_norm(t1), _norm(t2)])] = (match_num, t1, t2, ft1)

        written = 0
        for date_str in dates:
            try:
                events = get_scoreboard(date_str)
            except Exception as exc:  # noqa: BLE001
                db.log_collection(conn, "espn", "live_result", date_str, "error", str(exc))
                continue

            for ev in events:
                comp = ev["competitions"][0]
                status = comp["status"]["type"]
                # STRICT: only genuinely completed matches
                if not (status.get("completed") and status.get("state") == "post"):
                    continue

                scores = {}
                for c in comp["competitors"]:
                    scores[_norm(c["team"]["displayName"])] = c.get("score")
                names = list(scores.keys())
                if len(names) != 2 or any(scores[n] is None for n in names):
                    continue

                key = frozenset(names)
                row = by_pair.get(key)
                if not row:
                    continue
                match_num, t1, t2, existing_ft = row
                if existing_ft is not None:
                    continue  # already have a score (openfootball or prior run)

                # orient scores to our team1/team2
                s_t1 = int(scores[_norm(t1)])
                s_t2 = int(scores[_norm(t2)])
                with conn.cursor() as c2:
                    c2.execute("""
                        UPDATE worldcup_matches
                        SET score_ft_team1 = %s, score_ft_team2 = %s
                        WHERE match_num = %s AND score_ft_team1 IS NULL
                    """, (s_t1, s_t2, match_num))
                written += 1
                print(f"Wrote provisional final: {t1} {s_t1}-{s_t2} {t2} (match {match_num}, via ESPN)")

        conn.commit()
        db.log_collection(conn, "espn", "live_result", ",".join(dates), "success",
                           f"{written} provisional finals written")
        if written == 0:
            print("No newly-completed matches to write (nothing finished-and-missing).")
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    collect(dates=sys.argv[1:] or None)
