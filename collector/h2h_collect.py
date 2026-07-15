"""
Collect real head-to-head history from ESPN's summary endpoint
(headToHeadGames field) -- structured dates/scores/competitions, auto-
refreshable, unlike the 5 manually-typed WC-only rows from notes.txt.

Note: ESPN's feed appears to return only the last ~5 meetings (a "recent
h2h" convention, not full history), so it doesn't strictly extend coverage
depth -- but it's automated, self-updating, and includes non-World-Cup
meetings (friendlies) the manual table didn't have.

Usage:
    python h2h_collect.py <espn_event_id>
"""
import sys

from dotenv import load_dotenv

load_dotenv()

import db
import espn_collect


def collect(event_id: str):
    conn = db.connect()
    try:
        data = espn_collect.get_summary(event_id)
        h2h = data.get("headToHeadGames") or []
        if not h2h:
            print("No headToHeadGames data for this event.")
            return

        team1 = h2h[0]["team"]["displayName"]
        team2 = h2h[0]["events"][0]["opponent"]["displayName"] if h2h[0]["events"] else None
        count = 0
        for e in h2h[0]["events"]:
            year = int(e["gameDate"][:4])
            opp = e["opponent"]["displayName"]
            score = e["score"]
            comp = e.get("leagueName") or e.get("competitionName") or ""
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO h2h_history (team1, team2, year, round, score_summary, notes, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (team1, opp, year, comp, f"{team1} {score} {opp}",
                      f"gameDate={e['gameDate'][:10]}", "espn:headToHeadGames"))
            count += 1
        conn.commit()
        db.log_collection(conn, "espn", "h2h", f"event:{event_id}", "success", f"{count} h2h rows")
        print(f"Stored {count} H2H rows for {team1} vs {team2 or '?'}")
    finally:
        conn.close()


if __name__ == "__main__":
    collect(sys.argv[1])
