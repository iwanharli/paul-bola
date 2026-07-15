"""
Open-Meteo weather collector -> db_boforecasting.match_weather.

Free, no key required. Fills the weather gap notes.txt flagged (Atlanta heat +
humidity as a stamina factor). Uses forecast/historical-forecast endpoint --
Open-Meteo serves both past and future dates from the same API.

    GET https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..
        &hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m
        &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&timezone=..

Usage:
    python weather_collect.py <ground> <lat> <lon> <date_YYYY-MM-DD> <kickoff_hour_local> <timezone>

Example:
    python weather_collect.py "Atlanta" 33.7554 -84.4008 2026-07-15 15 "America/New_York"
"""
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

import db

BASE = "https://api.open-meteo.com/v1/forecast"


def collect(ground: str, lat: float, lon: float, date: str, kickoff_hour: int, tz: str):
    resp = requests.get(BASE, params={
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "start_date": date, "end_date": date, "timezone": tz,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    hourly = data["hourly"]

    idx = kickoff_hour
    conn = db.connect()
    try:
        db.upsert_composite(conn, "match_weather", {
            "ground": ground,
            "match_date": date,
            "kickoff_hour_local": kickoff_hour,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": hourly["temperature_2m"][idx],
            "humidity_pct": hourly["relative_humidity_2m"][idx],
            "precipitation_mm": hourly["precipitation"][idx],
            "wind_speed_kmh": hourly["wind_speed_10m"][idx],
            "raw": data,
        }, ["ground", "match_date"])
        conn.commit()
        db.log_collection(conn, "open-meteo", "weather", f"{ground}/{date}", "success",
                           f"{hourly['temperature_2m'][idx]}C, {hourly['relative_humidity_2m'][idx]}% humidity")
        print(f"{ground} {date} {kickoff_hour}:00 local -> "
              f"{hourly['temperature_2m'][idx]}C, {hourly['relative_humidity_2m'][idx]}% humidity, "
              f"wind {hourly['wind_speed_10m'][idx]}km/h")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 7:
        print(__doc__)
        sys.exit(1)
    ground, lat, lon, date, hour, tz = sys.argv[1:7]
    collect(ground, float(lat), float(lon), date, int(hour), tz)


if __name__ == "__main__":
    main()
