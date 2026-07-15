-- Schema for bola-forecasting: raw data collected from TheStatsAPI,
-- structured for a Dixon-Coles / Poisson xG prediction model.

-- Frozen pre-match predictions. A forecast must be locked BEFORE kickoff --
-- if it kept recomputing after the match (once the result enters the training
-- set), it would no longer be a prediction, just hindsight. export writes the
-- latest pre-match prediction here each run; once kickoff passes (or the match
-- is finished), it stops updating and serves the frozen value alongside the
-- actual result.
CREATE TABLE IF NOT EXISTS frozen_predictions (
    match_key    TEXT PRIMARY KEY,      -- e.g. 'eng-arg-sf', 'final-spain-argentina'
    kickoff_utc  TIMESTAMPTZ,
    prediction   JSONB NOT NULL,
    frozen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked       BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS competitions (
    id              BIGINT PRIMARY KEY,       -- TheStatsAPI competition_id
    name            TEXT NOT NULL,
    country         TEXT,
    type            TEXT,                     -- league, cup, international, etc.
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams (
    id              BIGINT PRIMARY KEY,       -- TheStatsAPI team_id
    name            TEXT NOT NULL,
    country         TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS matches (
    id              BIGINT PRIMARY KEY,       -- TheStatsAPI match_id
    competition_id  BIGINT REFERENCES competitions(id),
    season_id       BIGINT,
    stage           TEXT,
    matchday        INTEGER,
    kickoff_utc     TIMESTAMPTZ,
    status          TEXT,
    home_team_id    BIGINT REFERENCES teams(id),
    away_team_id    BIGINT REFERENCES teams(id),
    home_score      INTEGER,
    away_score      INTEGER,
    venue           TEXT,
    referee         TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_id);
CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id);

-- One row per team per match (so home + away = 2 rows per match),
-- which maps directly onto Dixon-Coles attack/defense strength inputs.
CREATE TABLE IF NOT EXISTS match_stats (
    match_id        BIGINT NOT NULL REFERENCES matches(id),
    team_id         BIGINT NOT NULL REFERENCES teams(id),
    is_home         BOOLEAN NOT NULL,
    xg              NUMERIC,
    xg_first_half   NUMERIC,
    xg_second_half  NUMERIC,
    shots           INTEGER,
    shots_on_target INTEGER,
    possession_pct  NUMERIC,
    passes          INTEGER,
    corners         INTEGER,
    fouls           INTEGER,
    yellow_cards    INTEGER,
    red_cards       INTEGER,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, team_id)
);

-- NOTE: the original TheStatsAPI-era `players` and `player_match_stats` tables
-- were dropped -- they were always empty (TheStatsAPI access was revoked) and
-- superseded by fifa_squads + player_crosswalk (identities) and
-- fifa_shot_events + asa_player_game_xg (per-player/per-match xG).

-- Raw shot events from FIFA's official public match-centre API
-- (api.fifa.com/api/v3/timelines/...), used to compute our own xG for World
-- Cup 2026 matches since no source provides ready-made xG for this tournament.
CREATE TABLE IF NOT EXISTS fifa_shot_events (
    event_id        BIGINT PRIMARY KEY,
    match_id         BIGINT NOT NULL,
    team_id          BIGINT,
    player_id        BIGINT,
    minute           TEXT,
    period           INTEGER,
    position_x       NUMERIC,
    position_y       NUMERIC,
    event_type       INTEGER,
    event_type_desc  TEXT,
    description      TEXT,
    is_goal          BOOLEAN,
    raw              JSONB,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fifa_shot_events_match ON fifa_shot_events(match_id);

-- Understat-sourced club league xG for the current running season (2025/26),
-- kept apart from `matches`/`match_stats` because Understat gives team names
-- (not TheStatsAPI-style team_id) and a per-match win-prob forecast.
CREATE TABLE IF NOT EXISTS understat_matches (
    id              BIGINT PRIMARY KEY,       -- Understat match id
    league          TEXT NOT NULL,
    season          TEXT NOT NULL,
    kickoff_utc     TIMESTAMPTZ,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    home_goals      INTEGER,
    away_goals      INTEGER,
    home_xg         NUMERIC,
    away_xg         NUMERIC,
    forecast_win    NUMERIC,
    forecast_draw   NUMERIC,
    forecast_loss   NUMERIC,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_understat_matches_teams ON understat_matches(home_team, away_team);

-- Separate, source-native table for World Cup 2026 fixtures/results from
-- openfootball/worldcup.json. Kept apart from matches/match_stats because that
-- source has no team_id/xG, just team names and goal scorers.
CREATE TABLE IF NOT EXISTS worldcup_matches (
    tournament      TEXT NOT NULL DEFAULT 'World Cup 2026',
    match_num       INTEGER NOT NULL,
    round           TEXT,
    match_date      DATE,
    match_time      TEXT,
    team1           TEXT NOT NULL,
    team2           TEXT NOT NULL,
    score_ht_team1  INTEGER,
    score_ht_team2  INTEGER,
    score_ft_team1  INTEGER,
    score_ft_team2  INTEGER,
    score_et_team1  INTEGER,
    score_et_team2  INTEGER,
    score_pens_team1 INTEGER,
    score_pens_team2 INTEGER,
    goals1          JSONB,
    goals2          JSONB,
    ground          TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tournament, match_num)
);

-- American Soccer Analysis (app.americansocceranalysis.com/api/v1) -- free,
-- no key required -- fills the MLS gap that Understat doesn't cover. Needed
-- specifically for Messi's current club form (Inter Miami CF, MLS 2026).
-- Per-game (not just season-aggregate) MLS xG splits, needed so Messi's
-- club-form granularity matches what Understat gives European-league
-- players (Bellingham etc get ~38 per-match rows; Messi previously had only
-- 1 season-aggregate row from asa_player_season_xg, a much thinner sample).
CREATE TABLE IF NOT EXISTS asa_player_game_xg (
    player_id           TEXT NOT NULL,
    game_id             TEXT NOT NULL,
    team_id             TEXT NOT NULL,
    season_name         TEXT NOT NULL,
    game_date_utc       TIMESTAMPTZ,
    minutes_played      INTEGER,
    shots               INTEGER,
    shots_on_target     INTEGER,
    goals               INTEGER,
    xgoals              NUMERIC,
    key_passes          INTEGER,
    primary_assists     INTEGER,
    xassists            NUMERIC,
    raw                 JSONB,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, game_id)
);

CREATE TABLE IF NOT EXISTS asa_player_season_xg (
    player_id           TEXT NOT NULL,
    team_id             TEXT NOT NULL,
    season_name         TEXT NOT NULL,
    player_name         TEXT NOT NULL,
    general_position    TEXT,
    minutes_played      INTEGER,
    shots               INTEGER,
    shots_on_target     INTEGER,
    goals               INTEGER,
    xgoals              NUMERIC,
    key_passes          INTEGER,
    primary_assists     INTEGER,
    xassists            NUMERIC,
    goals_plus_primary_assists NUMERIC,
    xgoals_plus_xassists NUMERIC,
    raw                 JSONB,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, season_name)
);

-- FIFA official squad lists (from the /live/football endpoint), fills the
-- previously-empty `players` table so national-team players can be linked to
-- their club-level base rates (asa_player_season_xg, understat_matches, etc).
-- IdPlayer here is FIFA's own id -- NOT the same namespace as ASA/Understat
-- ids, so cross-source player linking still has to go through name matching.
CREATE TABLE IF NOT EXISTS fifa_squads (
    fifa_player_id  BIGINT NOT NULL,
    fifa_team_id    BIGINT NOT NULL,
    player_name     TEXT NOT NULL,
    shirt_number    INTEGER,
    position        INTEGER,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fifa_player_id, fifa_team_id)
);

-- Match officials from the FIFA calendar endpoint (already fetched for
-- fifa_shot_events/fifa_squads, so this is free -- no extra API calls).
-- No referee tendency/history data exists anywhere free; this is just names.
CREATE TABLE IF NOT EXISTS fifa_match_officials (
    fifa_match_id   BIGINT NOT NULL,
    official_id     BIGINT NOT NULL,
    name            TEXT NOT NULL,
    role            TEXT,          -- Referee, Fourth official, VAR, etc.
    country         TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fifa_match_id, official_id)
);

-- FIFA calendar match index, so source-native fifa_match_id can be matched back
-- to our worldcup_matches/home-away/date rows. Used by export_predictions.py to
-- attach official referee assignments to upcoming/scenario matches.
CREATE TABLE IF NOT EXISTS fifa_match_index (
    fifa_match_id   BIGINT PRIMARY KEY,
    id_stage        BIGINT,
    match_date      DATE,
    kickoff_utc     TIMESTAMPTZ,
    home_team       TEXT,
    away_team       TEXT,
    ground          TEXT,
    status          TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- FIFA live match-centre lineups / match sheet. For upcoming matches this may
-- be squad-only until official lineups are published, so starter/status fields
-- are nullable and raw is kept for audit.
CREATE TABLE IF NOT EXISTS fifa_match_lineups (
    fifa_match_id   BIGINT NOT NULL,
    fifa_team_id    BIGINT,
    team_name       TEXT NOT NULL,
    fifa_player_id  BIGINT NOT NULL,
    player_name     TEXT NOT NULL,
    shirt_number    INTEGER,
    position        INTEGER,
    starter         BOOLEAN,
    captain         BOOLEAN,
    status          TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fifa_match_id, fifa_player_id)
);

-- Crosswalk linking the same real-world player across FIFA/ESPN/ASA, whose
-- player-id namespaces don't overlap. Built by normalized-name matching
-- (accent/case-insensitive) since none of these sources share a common id.
-- match_method records how a row was produced so low-confidence matches can
-- be audited/overridden later.
CREATE TABLE IF NOT EXISTS player_crosswalk (
    id                  SERIAL PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    fifa_player_id      BIGINT,
    fifa_team_id        BIGINT,
    espn_athlete_id     BIGINT,
    espn_team_name      TEXT,
    asa_player_id       TEXT,
    match_method        TEXT NOT NULL,  -- 'normalized_name_exact', 'manual', etc.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- StatsBomb open-data shots from recent international tournaments (WC2022,
-- Euro2024, Copa America 2024), used purely to enlarge the training set for
-- our coordinate-based xG model. Shot quality (goal probability given
-- location) is stable across tournaments, so pooling ~3-4k more shots makes
-- the distance/angle coefficients more robust than fitting on WC2026's 2745
-- shots alone. statsbomb_xg is their proprietary xG, kept only to validate
-- our simpler model's calibration -- not used as a feature.
CREATE TABLE IF NOT EXISTS statsbomb_shots (
    id              SERIAL PRIMARY KEY,
    competition     TEXT NOT NULL,
    match_id        BIGINT NOT NULL,
    location_x      NUMERIC,   -- 0-120 grid, goal at x=120
    location_y      NUMERIC,   -- 0-80 grid, goal centre at y=40
    is_goal         BOOLEAN,
    statsbomb_xg    NUMERIC,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_statsbomb_shots_match ON statsbomb_shots(match_id);

-- World Football Elo Ratings (eloratings.net/World.tsv, free, no key) --
-- fills the opponent-strength gap: the 6 knockout opponents Argentina/England
-- faced this tournament vary wildly in quality (Algeria/Jordan vs Switzerland,
-- Panama/Ghana vs Mexico/Norway), and nothing in the collected data adjusted
-- for that until now. Use elo as a covariate/prior when computing attack and
-- defense strength from the small (6-match) samples.
CREATE TABLE IF NOT EXISTS team_elo_ratings (
    country_code    TEXT NOT NULL,
    team_name       TEXT NOT NULL,
    elo             NUMERIC NOT NULL,
    world_rank      INTEGER,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (country_code, snapshot_date)
);

-- Real penalty-shootout kick-by-kick history from StatsBomb open data
-- (period=5 events), covering every shootout in WC2022/Euro2024/Copa2024.
-- Built to replace the model's hardcoded 50/50 shootout-win assumption with
-- an actual goalkeeper save rate where the sample supports it (e.g. Emiliano
-- Martinez faced 9 shots across 2 shootouts in WC2022, stopping 4 --  a
-- concrete number instead of relying on reputation alone). Small samples are
-- still small samples -- see keeper_shootout_summary for n before trusting.
CREATE TABLE IF NOT EXISTS shootout_history (
    id                  SERIAL PRIMARY KEY,
    tournament          TEXT NOT NULL,
    match_id            BIGINT NOT NULL,
    kick_order          INTEGER NOT NULL,
    kicking_team        TEXT NOT NULL,
    kicker_name         TEXT NOT NULL,
    outcome             TEXT NOT NULL,   -- 'Goal', 'Saved', 'Off T', 'Post', etc.
    opposing_team       TEXT NOT NULL,
    opposing_goalkeeper TEXT,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (match_id, kick_order)
);

-- Manually curated head-to-head history for a specific matchup, since no free
-- API offers structured H2H going back to 1962. Sourced from notes.txt.
CREATE TABLE IF NOT EXISTS h2h_history (
    id              SERIAL PRIMARY KEY,
    team1           TEXT NOT NULL,
    team2           TEXT NOT NULL,
    year            INTEGER NOT NULL,
    round           TEXT,
    score_summary   TEXT NOT NULL,   -- e.g. "Argentina 2-1 England"
    winner          TEXT,            -- NULL for draws decided outside normal play is still recorded via note
    notes           TEXT,
    source          TEXT NOT NULL DEFAULT 'manual:notes.txt',
    UNIQUE (team1, team2, year, score_summary)
);

-- ESPN's public site API (site.api.espn.com, free, no key) fills three gaps
-- FIFA's API couldn't: starting XI (roster[].starter flag), team-level match
-- stats (possession/shots/corners/fouls/cards), and structured bookmaker odds.
CREATE TABLE IF NOT EXISTS espn_match_rosters (
    espn_event_id   BIGINT NOT NULL,
    espn_athlete_id BIGINT NOT NULL,
    team_name       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    jersey          TEXT,
    starter         BOOLEAN,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (espn_event_id, espn_athlete_id)
);

CREATE TABLE IF NOT EXISTS espn_match_team_stats (
    espn_event_id     BIGINT NOT NULL,
    team_name         TEXT NOT NULL,
    possession_pct    NUMERIC,
    total_shots       INTEGER,
    fouls_committed   INTEGER,
    yellow_cards      INTEGER,
    red_cards         INTEGER,
    offsides          INTEGER,
    won_corners       INTEGER,
    saves             INTEGER,
    raw               JSONB,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (espn_event_id, team_name)
);

CREATE TABLE IF NOT EXISTS espn_match_odds (
    espn_event_id   BIGINT NOT NULL,
    provider        TEXT NOT NULL,
    details         TEXT,
    over_under      NUMERIC,
    spread          NUMERIC,
    home_moneyline  NUMERIC,
    away_moneyline  NUMERIC,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (espn_event_id, provider)
);

-- Weather at kickoff for each match venue (Open-Meteo, free, no key).
CREATE TABLE IF NOT EXISTS match_weather (
    id              SERIAL PRIMARY KEY,
    ground          TEXT NOT NULL,
    match_date      DATE NOT NULL,
    kickoff_hour_local INTEGER,
    latitude        NUMERIC,
    longitude       NUMERIC,
    temperature_c   NUMERIC,
    humidity_pct    NUMERIC,
    precipitation_mm NUMERIC,
    wind_speed_kmh  NUMERIC,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ground, match_date)
);

-- Referee card tendency, computed from our own collected data (fifa_match_
-- officials + espn_match_team_stats) rather than a new source -- there's no
-- shared id linking ESPN's and FIFA's match-id namespaces, so this required
-- manually cross-referencing by date/teams for the matches a referee took.
-- Sample sizes here are intentionally small (2-3 matches); treat as a weak
-- prior, not a reliable rate.
CREATE TABLE IF NOT EXISTS referee_tendency (
    id                  SERIAL PRIMARY KEY,
    referee_name        TEXT NOT NULL,
    tournament          TEXT NOT NULL DEFAULT 'World Cup 2026',
    matches_sampled     INTEGER NOT NULL,
    avg_yellow_per_match NUMERIC,
    avg_red_per_match   NUMERIC,
    notes               TEXT,
    source              TEXT NOT NULL DEFAULT 'derived:fifa_match_officials+espn_match_team_stats',
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Manually curated injury/suspension status for the semifinal, since no free
-- structured API exposes this (FIFA's /live endpoint Players[].SpecialStatus
-- was null pre-match) -- captured from web search coverage close to kickoff,
-- same manual treatment as h2h_history/match_odds_snapshot.
CREATE TABLE IF NOT EXISTS player_availability (
    id              SERIAL PRIMARY KEY,
    team            TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    status          TEXT NOT NULL,   -- 'out', 'doubtful', 'suspended', 'fit'
    reason          TEXT,
    match_context   TEXT NOT NULL,   -- e.g. 'WC2026 Semifinal ENG vs ARG'
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          TEXT NOT NULL DEFAULT 'manual:web_search'
);

-- Manually captured market odds snapshot(s) for calibration/backtesting our
-- own model's probabilities against the market. No free odds API exists for
-- one-off international matches without a paid key + query quota, so this is
-- captured by hand from sportsbook sites via web search, same treatment as
-- h2h_history.
CREATE TABLE IF NOT EXISTS match_odds_snapshot (
    id              SERIAL PRIMARY KEY,
    team1           TEXT NOT NULL,
    team2           TEXT NOT NULL,
    match_date      DATE,
    bookmaker       TEXT NOT NULL,
    market          TEXT NOT NULL,     -- e.g. '90min_moneyline', 'to_advance'
    team1_odds      TEXT,              -- American odds as given, e.g. '+200'
    draw_odds       TEXT,
    team2_odds      TEXT,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes           TEXT,
    source          TEXT NOT NULL DEFAULT 'manual:web_search'
);

ALTER TABLE match_odds_snapshot ADD COLUMN IF NOT EXISTS source_event_id TEXT;
ALTER TABLE match_odds_snapshot ADD COLUMN IF NOT EXISTS sport_key TEXT;
ALTER TABLE match_odds_snapshot ADD COLUMN IF NOT EXISTS commence_time TIMESTAMPTZ;
ALTER TABLE match_odds_snapshot ADD COLUMN IF NOT EXISTS raw JSONB;

-- football-data.org (requires free API token) fallback data. Stored separately
-- because its IDs and coverage differ from openfootball/FIFA/ESPN.
CREATE TABLE IF NOT EXISTS football_data_matches (
    fd_match_id     BIGINT PRIMARY KEY,
    competition     TEXT,
    season          TEXT,
    match_date      DATE,
    kickoff_utc     TIMESTAMPTZ,
    stage           TEXT,
    status          TEXT,
    home_team       TEXT,
    away_team       TEXT,
    home_score      INTEGER,
    away_score      INTEGER,
    referees        JSONB,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Wikidata metadata (no key) for teams and venues: stable entity ids,
-- coordinates, images/Commons links, and raw claims for later enrichment.
CREATE TABLE IF NOT EXISTS wikidata_entities (
    entity_type     TEXT NOT NULL, -- team, venue, country, player
    name            TEXT NOT NULL,
    wikidata_id     TEXT,
    label           TEXT,
    description     TEXT,
    latitude        NUMERIC,
    longitude       NUMERIC,
    image_url       TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_type, name)
);

-- Generic raw store for optional registered providers (API-FOOTBALL,
-- Sportmonks). These can cover lineups, injuries, odds, referee, statistics,
-- and predictions depending on plan/quota.
CREATE TABLE IF NOT EXISTS provider_match_context (
    provider        TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    match_date      DATE,
    home_team       TEXT,
    away_team       TEXT,
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, endpoint, external_id)
);

-- Derived, non-official projected XI source. This is deliberately separate
-- from fifa_match_lineups because it is based on recent ESPN starter frequency
-- and FIFA squad fallback, not confirmed team sheets.
CREATE TABLE IF NOT EXISTS projected_team_lineups (
    team_name       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    shirt_number    INTEGER,
    position        INTEGER,
    starts          INTEGER NOT NULL DEFAULT 0,
    appearances     INTEGER NOT NULL DEFAULT 0,
    confidence      NUMERIC,
    source          TEXT NOT NULL,
    raw             JSONB,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_name, player_name)
);

-- Team-news coverage marker from official squad feeds. This does not claim
-- everyone is fit; it records whether a source has any special status rows.
CREATE TABLE IF NOT EXISTS team_availability_coverage (
    team_name       TEXT PRIMARY KEY,
    player_count    INTEGER NOT NULL,
    special_status_count INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL,
    raw             JSONB,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Derived player attack summary for teams with no actual scorer yet. Lets the
-- frontend show "top attackers/shooters" instead of an empty top-scorers panel.
CREATE TABLE IF NOT EXISTS team_player_attack_summary (
    team_name       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    goals           INTEGER NOT NULL DEFAULT 0,
    shots           INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL,
    raw             JSONB,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_name, player_name)
);

-- Tracks which (competition_id, season_id) pairs and endpoints have already
-- been pulled, so the collector can resume without re-fetching everything.
CREATE TABLE IF NOT EXISTS collection_log (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,            -- e.g. 'thestatsapi'
    endpoint        TEXT NOT NULL,             -- e.g. 'matches', 'match_stats'
    scope           TEXT NOT NULL,             -- e.g. 'competition:2000/season:2026'
    status          TEXT NOT NULL,             -- 'success', 'partial', 'error'
    detail          TEXT,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Views placed last (not near the tables they were originally documented
-- next to) because CREATE VIEW is evaluated at each execution in file order --
-- a view referencing a table defined LATER in this script fails on a fresh
-- database (only worked on existing databases where tables were added
-- incrementally over time, never applied to an empty DB in one shot).

-- Reconciliation view: FIFA's shot-event count doesn't match ESPN's official
-- totalShots on cross-check (e.g. Argentina vs Switzerland: FIFA counted 25,
-- ESPN reported 22) -- likely a differing definition of "shot" (blocked
-- attempts included/excluded). Treat ESPN as ground truth for shot VOLUME;
-- fifa_shot_events remains useful only for shot LOCATION (xG modeling from
-- coordinates), not for total counts.
CREATE OR REPLACE VIEW v_match_shot_counts_reliable AS
SELECT espn_event_id, team_name, total_shots AS reliable_total_shots
FROM espn_match_team_stats;

-- Reconciliation view: fifa_shot_events.is_goal undercounts goals on ~1/3 of
-- matches (the FIFA public timeline feed silently drops some goal events --
-- confirmed by cross-checking against worldcup_matches, whose goals1/goals2
-- scorer lists matched official scores on all 12 checked matches). Treat
-- worldcup_matches as the ground truth for goal counts/timing/scorers; use
-- fifa_shot_events only for shot locations (attempt coordinates) feeding xG.
CREATE OR REPLACE VIEW v_match_goal_counts_reliable AS
SELECT
    team1, team2, match_num,
    COALESCE(score_et_team1, score_ft_team1) AS team1_goals,
    COALESCE(score_et_team2, score_ft_team2) AS team2_goals,
    jsonb_array_length(goals1) AS team1_scorer_count,
    jsonb_array_length(goals2) AS team2_scorer_count
FROM worldcup_matches;
