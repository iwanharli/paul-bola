"""
Wikidata metadata collector -> wikidata_entities.

No registration/API key. It searches current teams and venues, stores entity id,
description, image, and coordinates when available.
"""
import requests
import time
from dotenv import load_dotenv

load_dotenv()

import db

API = "https://www.wikidata.org/w/api.php"
ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
HEADERS = {"User-Agent": "bola-forecasting/1.0 (local research collector)"}

VENUE_QUERIES = {
    "New York/New Jersey (East Rutherford)": "MetLife Stadium",
    "Miami (Miami Gardens)": "Hard Rock Stadium",
    "Dallas (Arlington)": "AT&T Stadium",
    "Los Angeles (Inglewood)": "SoFi Stadium",
    "San Francisco Bay Area (Santa Clara)": "Levi's Stadium",
    "Guadalajara (Zapopan)": "Estadio Akron",
    "Monterrey (Guadalupe)": "Estadio BBVA",
    "Boston (Foxborough)": "Gillette Stadium",
    "Atlanta": "Mercedes-Benz Stadium",
    "Kansas City": "Arrowhead Stadium",
    "Seattle": "Lumen Field",
    "Philadelphia": "Lincoln Financial Field",
    "Houston": "NRG Stadium",
    "Toronto": "BMO Field",
    "Vancouver": "BC Place",
    "Mexico City": "Estadio Azteca",
}


def _request(url, **kwargs):
    for attempt in range(4):
        resp = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        time.sleep(2.0 * (attempt + 1))
    resp.raise_for_status()


def _search(query):
    resp = _request(API, params={
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": query,
        "limit": 1,
    })
    rows = resp.json().get("search", [])
    time.sleep(0.25)
    return rows[0] if rows else None


def _entity(qid):
    resp = _request(ENTITY.format(qid=qid))
    time.sleep(0.25)
    return resp.json().get("entities", {}).get(qid, {})


def _claim(entity, pid):
    claims = entity.get("claims", {}).get(pid, [])
    if not claims:
        return None
    return claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")


def _coords(entity):
    value = _claim(entity, "P625")
    if not isinstance(value, dict):
        return None, None
    return value.get("latitude"), value.get("longitude")


def _image(entity):
    value = _claim(entity, "P18")
    if not value:
        return None
    filename = str(value).replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"


def _names(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT team FROM (
                SELECT team1 AS team FROM worldcup_matches
                UNION SELECT team2 AS team FROM worldcup_matches
            ) t
            WHERE team IS NOT NULL AND team NOT LIKE 'W%%' AND team NOT LIKE 'L%%'
            ORDER BY team
        """)
        teams = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT DISTINCT ground FROM worldcup_matches WHERE ground IS NOT NULL ORDER BY ground")
        venues = [row[0] for row in cur.fetchall()]
    return teams, venues


def _existing(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT entity_type, name FROM wikidata_entities WHERE wikidata_id IS NOT NULL")
        return set(cur.fetchall())


def _ensure_placeholders(conn, teams, venues):
    with conn.cursor() as cur:
        for team in teams:
            cur.execute("""
                INSERT INTO wikidata_entities
                    (entity_type, name, wikidata_id, label, description, latitude, longitude, image_url, raw)
                VALUES (%s, %s, NULL, %s, %s, NULL, NULL, NULL, '{"status":"placeholder"}'::jsonb)
                ON CONFLICT (entity_type, name) DO NOTHING
            """, ("team", team, team, "Pending Wikidata enrichment"))
        for venue in venues:
            cur.execute("""
                INSERT INTO wikidata_entities
                    (entity_type, name, wikidata_id, label, description, latitude, longitude, image_url, raw)
                VALUES (%s, %s, NULL, %s, %s, NULL, NULL, NULL, '{"status":"placeholder"}'::jsonb)
                ON CONFLICT (entity_type, name) DO NOTHING
            """, ("venue", venue, VENUE_QUERIES.get(venue, venue), "Pending Wikidata enrichment"))
    conn.commit()


def _store(conn, entity_type, name, query):
    hit = _search(query)
    if not hit:
        return False
    qid = hit.get("id")
    entity = _entity(qid)
    lat, lon = _coords(entity)
    db.upsert_composite(conn, "wikidata_entities", {
        "entity_type": entity_type,
        "name": name,
        "wikidata_id": qid,
        "label": hit.get("label"),
        "description": hit.get("description"),
        "latitude": lat,
        "longitude": lon,
        "image_url": _image(entity),
        "raw": {"search": hit, "entity": entity},
    }, ["entity_type", "name"])
    return True


def collect(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
    try:
        teams, venues = _names(conn)
        _ensure_placeholders(conn, teams, venues)
        seen = _existing(conn)
        count = 0
        try:
            for team in teams:
                if ("team", team) in seen:
                    continue
                count += int(_store(conn, "team", team, f"{team} national football team"))
                conn.commit()
            for venue in venues:
                if ("venue", venue) in seen:
                    continue
                count += int(_store(conn, "venue", venue, VENUE_QUERIES.get(venue, venue)))
                conn.commit()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                db.log_collection(conn, "wikidata", "entities", "teams+venues", "partial", f"rate limited after {count} new entities")
                print(f"Wikidata rate-limited after {count} new entities; rerun later to resume")
                return
            raise
        db.log_collection(conn, "wikidata", "entities", "teams+venues", "success", f"{count} entities")
        print(f"Wikidata stored {count} entities")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, "wikidata", "entities", "teams+venues", "error", str(exc))
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    collect()
