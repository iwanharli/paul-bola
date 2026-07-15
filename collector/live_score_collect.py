"""
Live in-progress scores -> frontend/public/live.json (+ dist).

DISPLAY ONLY. This deliberately does NOT touch the database: a live score is
provisional and must never be written as a final result (that would corrupt
worldcup_matches and the frozen predictions). It writes a tiny separate
live.json that the frontend polls frequently, kept apart from the heavy
predictions.json so it can update on a fast cadence (see the paul-bola-live
PM2 app) without re-running the whole export.

Pulls ESPN's scoreboard and emits only matches ESPN marks in-progress
(state == "in"). When nothing is live, it writes an empty list -- the
frontend then shows no live overlay.

Usage:
    python live_score_collect.py
"""
import datetime
import json
import os

import requests

from config import ESPN_BASE as BASE
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUT_PATHS = ["../frontend/public/live.json", "../frontend/dist/live.json"]


def get_scoreboard(date_str):
    r = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("events", [])


def collect():
    now = datetime.datetime.now(datetime.timezone.utc)
    dates = [now.strftime("%Y%m%d"), (now - datetime.timedelta(days=1)).strftime("%Y%m%d")]

    live = []
    for date_str in dates:
        try:
            events = get_scoreboard(date_str)
        except Exception:  # noqa: BLE001 -- best effort, never crash the fast loop
            continue
        for ev in events:
            comp = ev["competitions"][0]
            st = comp["status"]["type"]
            if st.get("state") != "in":  # only genuinely in-progress
                continue
            teams = {}
            for c in comp["competitors"]:
                teams[c.get("homeAway")] = {"name": c["team"]["displayName"],
                                            "score": c.get("score")}
            if "home" not in teams or "away" not in teams:
                continue
            live.append({
                "home": teams["home"]["name"], "away": teams["away"]["name"],
                "homeScore": teams["home"]["score"], "awayScore": teams["away"]["score"],
                "minute": st.get("displayClock") or st.get("detail"),
                "detail": st.get("detail"),
            })

    payload = json.dumps({"updated": now.isoformat(timespec="seconds"), "matches": live}, indent=2)
    for path in OUT_PATHS:
        if not os.path.exists(os.path.dirname(path)):
            continue
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            f.write(payload)
        os.replace(tmp, path)
    print(f"live.json: {len(live)} match(es) in progress")


if __name__ == "__main__":
    collect()
