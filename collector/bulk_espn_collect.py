"""
One-off bulk collector: pulls ESPN roster/stats/odds for every World Cup 2026
match on the given list of dates (used to expand from Argentina/England-only
scope to the full tournament, needed for backtesting the model against every
finished match).

Usage:
    python bulk_espn_collect.py <dates_file>   # one YYYYMMDD per line
"""
import sys
import time

from dotenv import load_dotenv

load_dotenv()

import db
import espn_collect


def main():
    dates_file = sys.argv[1]
    with open(dates_file) as f:
        dates = [line.strip() for line in f if line.strip()]

    conn = db.connect()
    total_events = 0
    total_errors = 0
    try:
        for date_str in dates:
            events = espn_collect.get_scoreboard(date_str)
            print(f"{date_str}: {len(events)} events")
            for e in events:
                try:
                    espn_collect.collect_match(conn, e["id"])
                    total_events += 1
                except Exception as exc:  # noqa: BLE001
                    total_errors += 1
                    db.log_collection(conn, "espn", "bulk_match", f"event:{e['id']}", "error", str(exc))
                    print(f"  [FAIL] {e.get('name')}: {exc}")
                time.sleep(0.2)
    finally:
        conn.close()
    print(f"\nDone. {total_events} events collected, {total_errors} errors.")


if __name__ == "__main__":
    main()
