"""
Collect context for current late-tournament scenarios.

Currently this fills weather for unfinished World Cup matches (including final
scenario placeholders W102/L102) using the existing match_weather table.
Open-Meteo needs no registration/key.
"""
from dotenv import load_dotenv

load_dotenv()

import db
import weather_collect

GROUND_COORDS = {
    "Atlanta": (33.7554, -84.4008, "America/New_York"),
    "Mexico City": (19.4326, -99.1332, "America/Mexico_City"),
    "New York/New Jersey (East Rutherford)": (40.8135, -74.0745, "America/New_York"),
    "Miami (Miami Gardens)": (25.9580, -80.2389, "America/New_York"),
    "Boston (Foxborough)": (42.0909, -71.2643, "America/New_York"),
    "Dallas (Arlington)": (32.7473, -97.0945, "America/Chicago"),
    "Kansas City": (39.0489, -94.4839, "America/Chicago"),
    "Los Angeles (Inglewood)": (33.9535, -118.3392, "America/Los_Angeles"),
    "San Francisco Bay Area (Santa Clara)": (37.4030, -121.9700, "America/Los_Angeles"),
    "Seattle": (47.5952, -122.3316, "America/Los_Angeles"),
    "Philadelphia": (39.9008, -75.1675, "America/New_York"),
    "Houston": (29.6847, -95.4107, "America/Chicago"),
    "Toronto": (43.6332, -79.3892, "America/Toronto"),
    "Vancouver": (49.2767, -123.1120, "America/Vancouver"),
    "Guadalajara (Zapopan)": (20.6810, -103.4620, "America/Mexico_City"),
    "Monterrey (Guadalupe)": (25.6690, -100.2440, "America/Monterrey"),
}


def _hour(match_time):
    text = str(match_time or "")
    try:
        return int(text.split(":", 1)[0])
    except (TypeError, ValueError):
        return 15


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT match_num, round, match_date, match_time, ground
                FROM worldcup_matches
                WHERE score_ft_team1 IS NULL
                   OR round IN ('Semi-final', 'Match for third place', 'Final')
                ORDER BY match_date, match_num
            """)
            rows = cur.fetchall()

        count = 0
        skipped = 0
        for _match_num, _round, match_date, match_time, ground in rows:
            if ground not in GROUND_COORDS:
                skipped += 1
                continue
            lat, lon, tz = GROUND_COORDS[ground]
            weather_collect.collect(ground, lat, lon, str(match_date), _hour(match_time), tz)
            count += 1

        db.log_collection(conn, "open-meteo", "scenario_weather", "unfinished_matches", "success", f"{count} collected, {skipped} skipped")
        print(f"Scenario weather collected for {count} matches")
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
