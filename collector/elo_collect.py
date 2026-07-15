"""
World Football Elo Ratings collector -> db_boforecasting.team_elo_ratings.

Source: eloratings.net/World.tsv (free, no key). Fills the opponent-strength
gap -- lets the model discount/weight Argentina's and England's knockout
results by how strong each opponent actually was, instead of treating a win
over Algeria the same as a win over Switzerland.

Usage:
    python elo_collect.py
"""
import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

import db

URL = "https://www.eloratings.net/World.tsv"

# eloratings.net uses its own 2-letter codes, which mostly but not always
# match ISO 3166-1 alpha-2 (e.g. England is "EN", not "GB"). Mapped by hand
# for the teams relevant to this project's Argentina/England scope.
CODE_TO_NAME = {
    "AR": "Argentina", "EN": "England", "ES": "Spain", "FR": "France",
    "NO": "Norway", "CH": "Switzerland", "MX": "Mexico", "HR": "Croatia",
    "AT": "Austria", "DZ": "Algeria", "EG": "Egypt", "CD": "DR Congo",
    "PA": "Panama", "JO": "Jordan", "CV": "Cape Verde", "GH": "Ghana",
}


def collect():
    resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    lines = resp.text.strip().split("\n")

    conn = db.connect()
    try:
        count = 0
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            rank, _, code, elo = parts[0], parts[1], parts[2], parts[3]
            if code not in CODE_TO_NAME:
                continue
            db.upsert_composite(conn, "team_elo_ratings", {
                "country_code": code,
                "team_name": CODE_TO_NAME[code],
                "elo": float(elo),
                "world_rank": int(rank),
                "snapshot_date": datetime.date.today().isoformat(),
                "raw": {"line": line},
            }, ["country_code", "snapshot_date"])
            count += 1
        conn.commit()
        db.log_collection(conn, "eloratings.net", "world_elo", "snapshot", "success", f"{count} teams")
        print(f"Stored Elo ratings for {count} teams")
    finally:
        conn.close()


if __name__ == "__main__":
    collect()
