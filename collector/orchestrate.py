"""
Orchestrator for scheduled (cron / PM2) data collection -> db_boforecasting.

Runs unattended: auto-discovers what to refresh and runs every DYNAMIC
collector across the WHOLE tournament (not just Argentina/England). Safe to run
repeatedly -- every downstream collector upserts, so re-running just refreshes.

Each step is wrapped so one failure doesn't abort the run; failures are logged
to collection_log (status='error') for review.

WHAT THIS REFRESHES (dynamic, changes over the tournament):
  1. worldcup_matches (openfootball)          -- scores/scorers as matches finish
  2. team_elo_ratings (eloratings.net)        -- ratings drift over time
  3. ESPN roster/stats/odds for recently-finished + upcoming matches
  4. FIFA shot events (all finished matches)
  5. FIFA match officials, match index, and lineups/match sheet
  6. FIFA squads for teams appearing in the window
  7. weather for matches in the window + unfinished final scenarios
  8. optional registered providers when API keys are present:
     The Odds API, football-data.org, API-Football, Sportmonks
  9. player_crosswalk rebuild

WHAT IT DOES **NOT** REFETCH (by design -- documented so it's not a surprise):
  - Manual fallback rows in h2h_history, match_odds_snapshot,
    player_availability, referee_tendency. New optional collectors can now add
    sourced rows to these areas when credentials/coverage exist.
  - Static historical data: statsbomb_shots (WC2022/Euro2024/Copa2024) and the
    Understat/ASA club seasons (2025/26 is complete). Run their collectors
    once; set REFRESH_CLUB=1 in the env to force a re-pull anyway.

Usage:
    python orchestrate.py                 # dynamic refresh (default, for cron/PM2)
    python orchestrate.py --full          # also re-pull static/club sources once
"""
import datetime
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

import db
import worldcup_collect
import espn_collect
import fifa_collect
import fifa_officials_collect
import fifa_match_context_collect
import fifa_squads_collect
import elo_collect
import weather_collect
import final_scenarios_collect
import odds_api_collect
import football_data_collect
import api_football_collect
import sportmonks_collect
import wikidata_collect
import derived_context_collect
import build_player_crosswalk
import referee_tendency_collect
import h2h_collect
# weather_backfill imported lazily in its step to avoid a circular import
# (it reads GROUND_COORDS from this module).

# how many days back to look for matches whose data may still be settling
LOOKBACK_DAYS = 3

# venue coordinates for weather (extend as needed)
GROUND_COORDS = {
    "Atlanta": (33.7554, -84.4008), "Mexico City": (19.4326, -99.1332),
    "New York/New Jersey (East Rutherford)": (40.8135, -74.0745),
    "Miami (Miami Gardens)": (25.9580, -80.2389), "Boston (Foxborough)": (42.0909, -71.2643),
    "Dallas (Arlington)": (32.7473, -97.0945), "Kansas City": (39.0489, -94.4839),
    "Los Angeles (Inglewood)": (33.9535, -118.3392), "San Francisco Bay Area (Santa Clara)": (37.4030, -121.9700),
    "Seattle": (47.5952, -122.3316), "Philadelphia": (39.9008, -75.1675),
    "Houston": (29.6847, -95.4107), "Toronto": (43.6332, -79.3892),
    "Vancouver": (49.2767, -123.1120), "Guadalajara (Zapopan)": (20.6810, -103.4620),
    "Monterrey (Guadalupe)": (25.6690, -100.2440),
}


def safe_step(conn, source, step, fn):
    try:
        fn()
        db.log_collection(conn, source, "orchestrate_step", step, "success", "")
        print(f"[ok] {step}")
    except Exception as exc:  # noqa: BLE001
        db.log_collection(conn, source, "orchestrate_step", step, "error", str(exc))
        print(f"[FAIL] {step}: {exc}")


def run(full=False):
    conn = db.connect()
    try:
        # --- tournament-wide dynamic sources ---
        safe_step(conn, "openfootball", "refresh_worldcup_matches", worldcup_collect.collect)
        safe_step(conn, "eloratings", "refresh_elo", elo_collect.collect)
        safe_step(conn, "fifa", "refresh_officials", lambda: fifa_officials_collect.collect(conn))
        safe_step(conn, "fifa", "refresh_match_context", lambda: fifa_match_context_collect.collect(conn))
        safe_step(conn, "the-odds-api", "refresh_external_odds", lambda: odds_api_collect.collect(conn))
        safe_step(conn, "football-data.org", "refresh_football_data", lambda: football_data_collect.collect(conn))
        safe_step(conn, "api-football", "refresh_api_football", lambda: api_football_collect.collect(conn))
        safe_step(conn, "sportmonks", "refresh_sportmonks", lambda: sportmonks_collect.collect(conn))
        # NOTE: FIFA shots are pulled per-team-in-window below, not "all" every
        # run -- re-pulling 101 matches each 15-min cron would hammer the API.

        # --- per-match window (recently finished + today's upcoming) ---
        today = datetime.date.today()
        window = [today - datetime.timedelta(days=d) for d in range(LOOKBACK_DAYS + 1)]
        cur = conn.cursor()
        cur.execute("""
            SELECT match_num, team1, team2, match_date, ground, score_ft_team1
            FROM worldcup_matches
            WHERE match_date = ANY(%s)
        """, (window,))
        matches = cur.fetchall()
        print(f"{len(matches)} matches in the {LOOKBACK_DAYS}-day window")

        teams_seen = set()
        for match_num, team1, team2, match_date, ground, ft1 in matches:
            date_str = match_date.strftime("%Y%m%d")

            def do_espn(date_str=date_str, team1=team1, team2=team2):
                events = espn_collect.get_scoreboard(date_str)
                ev = next((e for e in events
                           if team1.lower() in e.get("name", "").lower()
                           and team2.lower() in e.get("name", "").lower()), None)
                if ev:
                    espn_collect.collect_match(conn, ev["id"])
            safe_step(conn, "espn", f"espn:{team1}_v_{team2}_{date_str}", do_espn)

            # squads + FIFA shots for both teams (idempotent; per-team scopes
            # the shot pull to teams actually playing in the window)
            for team in (team1, team2):
                if team and team not in teams_seen and not team.startswith(("W", "L")):
                    teams_seen.add(team)
                    safe_step(conn, "fifa", f"squad:{team}",
                              lambda team=team: fifa_squads_collect.collect_squad(conn, team))
                    safe_step(conn, "fifa", f"shots:{team}",
                              lambda team=team: fifa_collect.collect_shots(team))

            # weather for known venues
            if ground in GROUND_COORDS:
                lat, lon = GROUND_COORDS[ground]
                safe_step(conn, "open-meteo", f"weather:{ground}_{match_date}",
                          lambda g=ground, lat=lat, lon=lon, d=match_date:
                          weather_collect.collect(g, lat, lon, str(d), 15, "America/New_York"))

        safe_step(conn, "open-meteo", "refresh_final_scenario_weather",
                  lambda: final_scenarios_collect.collect(conn))

        # Historical weather never changes (past dates), so backfill it only on
        # --full, not every 15-min cron -- 99 API calls per run would be waste.
        if full or os.environ.get("REFRESH_WEATHER") == "1":
            def do_weather_backfill():
                import weather_backfill
                weather_backfill.collect(conn)
            safe_step(conn, "open-meteo", "backfill_historical_weather", do_weather_backfill)

        # --- static / club sources: only on --full or REFRESH_CLUB=1 ---
        if full or os.environ.get("REFRESH_CLUB") == "1":
            def do_club():
                import understat_collect, asa_collect
                uconn = db.connect()
                try:
                    client = __import__("understatapi").UnderstatClient()
                    for lg in understat_collect.LEAGUES:
                        understat_collect.collect_league(client, uconn, lg, "2025")
                    asa_collect.collect_season_xg(uconn, "2026")
                finally:
                    uconn.close()
            safe_step(conn, "club", "refresh_club_xg", do_club)

        # --- derived ---
        if full or os.environ.get("REFRESH_METADATA") == "1":
            safe_step(conn, "wikidata", "refresh_team_venue_metadata",
                      lambda: wikidata_collect.collect(conn))

        safe_step(conn, "internal", "rebuild_player_crosswalk", build_player_crosswalk.build)
        safe_step(conn, "internal", "refresh_derived_context", lambda: derived_context_collect.collect(conn))
        # Recomputes ALL 40+ referees' card tendency from data already
        # collected (fifa_match_officials x espn_match_team_stats) -- no new
        # external calls beyond a fresh ESPN scoreboard crosswalk pull.
        safe_step(conn, "internal", "refresh_referee_tendency", referee_tendency_collect.collect)
        # H2H for the hero Argentina/England matchup specifically (ESPN's
        # headToHeadGames, ~last 5 meetings, auto-refreshing).
        safe_step(conn, "espn", "refresh_h2h_eng_arg", lambda: h2h_collect.collect("760515"))

        # Regenerate the frontend's predictions.json from the just-refreshed DB.
        # Without this, PM2's cron keeps the database current but the site
        # keeps serving whatever JSON was last exported by hand -- a real gap
        # caught when dist/predictions.json was found stale against a fresh
        # DB. Run as a subprocess: export_predictions.py lives in ../model and
        # does its own sys.path/cwd-relative imports, which would collide if
        # imported directly into this module's path.
        def do_export():
            model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model")
            result = subprocess.run(
                [sys.executable, "export_predictions.py"],
                cwd=model_dir, capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:] or "export_predictions.py failed")
            print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "(no output)")
        safe_step(conn, "internal", "export_predictions_json", do_export)

        print("\nOrchestration run complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    run(full="--full" in sys.argv)
