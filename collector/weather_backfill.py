"""
Backfill weather for ALL finished World Cup 2026 matches with a known venue,
not just the recent rolling window the orchestrator covers. match_time already
carries the local kickoff hour + UTC offset (e.g. "20:00 UTC-5"), so we parse
the hour directly and let Open-Meteo resolve the venue timezone from
coordinates (timezone=auto). Keyed (ground, date) per the table's unique
constraint, so one reading per venue per day.

Usage:
    python weather_backfill.py
"""
import re

from dotenv import load_dotenv

load_dotenv()

import db
import weather_collect
from orchestrate import GROUND_COORDS


def collect(conn=None):
    own = conn is None
    if own:
        conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ground, match_date, match_time
            FROM worldcup_matches
            WHERE score_ft_team1 IS NOT NULL AND ground IS NOT NULL
            ORDER BY match_date
        """)
        rows = cur.fetchall()

        done, skipped = 0, 0
        seen = set()
        for ground, match_date, match_time in rows:
            if ground not in GROUND_COORDS:
                skipped += 1
                continue
            key = (ground, str(match_date))
            if key in seen:
                continue
            seen.add(key)

            m = re.match(r"(\d{1,2}):", match_time or "")
            hour = int(m.group(1)) if m else 15
            lat, lon = GROUND_COORDS[ground]
            try:
                weather_collect.collect(ground, lat, lon, str(match_date), hour, "auto")
                done += 1
            except Exception as exc:  # noqa: BLE001
                db.log_collection(conn, "open-meteo", "weather_backfill",
                                  f"{ground}/{match_date}", "error", str(exc))

        db.log_collection(conn, "open-meteo", "weather_backfill", "all_finished",
                           "success", f"{done} venues/dates, {skipped} unknown grounds")
        print(f"Backfilled weather for {done} venue-dates ({skipped} skipped: ground not in GROUND_COORDS)")
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    collect()
