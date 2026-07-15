// PM2 config for the data collector orchestrator.
// Deploy notes:
//   - Requires collector/venv/ (or an equivalent Python env with
//     requirements.txt installed) and collector/.env populated on the server.
//   - orchestrate.py is a one-shot script (not a long-running server), so we
//     use cron_restart to fire it on a schedule and autorestart:false so PM2
//     doesn't treat its normal exit as a crash.
//   - Default (dynamic) run refreshes tournament-wide match/odds/stats/shots/
//     squads/officials/weather/elo + rebuilds the crosswalk. It does NOT
//     re-pull static club data (Understat/ASA) or historical StatsBomb shots,
//     nor the manual tables (h2h/odds-snapshot/availability/referee-tendency).
//   - FIRST-TIME SETUP on a fresh DB, run these once before starting PM2:
//       ../venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); \
//         import db; c=db.connect(); db.apply_schema(c,'../db/schema.sql')"
//       ../venv/bin/python statsbomb_shots_collect.py     # static historical xG
//       ../venv/bin/python understat_collect.py all 2025  # club-form base rates
//       ../venv/bin/python asa_collect.py season 2026      # MLS (Messi) base rate
//       ../venv/bin/python orchestrate.py --full           # then a full seed run
//   - 15-min interval suits match-day cadence; all collectors upsert, so extra
//     runs are safe (just more calls against free/unauthenticated APIs).
module.exports = {
  apps: [
    {
      name: "bola-forecasting-collector",
      cwd: "./collector",
      script: "./venv/bin/python",
      args: "orchestrate.py",
      autorestart: false,
      cron_restart: "*/15 * * * *",
      watch: false,
      out_file: "../cron.log",
      error_file: "../cron.log",
      merge_logs: true,
    },
    // Serves frontend/dist as a static site (requires `npm run build` first
    // and the `serve` package installed -- see frontend/package.json). Port
    // is proxied by nginx (paul.kecup.in -> 127.0.0.1:13801), following this
    // server's existing convention of one PM2 process per site per port.
    {
      name: "paul-bola-fe-13801",
      cwd: "./frontend",
      script: "./node_modules/.bin/serve",
      args: "-s dist -l 13801",
      autorestart: true,
      watch: false,
      out_file: "../fe.log",
      error_file: "../fe.log",
      merge_logs: true,
    },
  ],
};
