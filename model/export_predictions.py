"""
Export model predictions to JSON for the frontend.

Reuses the deployable model (xG/goals blend + time decay + market blend) and
the penalty-aware scorer model, and writes a single predictions.json the React
app reads. Run after data collection / model changes:

    python export_predictions.py
"""
import datetime
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db
from xg_model import build_xg_match_table
from final_predict import (fit_all, score_matrix, BLEND_ALPHA,
                           ET_MINUTES_FRACTION, ET_INTENSITY, SHOOTOUT_ARG_WIN)
from compare_models import KNOCKOUT_START, fit, shrink, predict_result_probs
from scorer_model import (player_tournament_xg, unavailable_players,
                          penalty_takers_tournament, team_penalty_rate, scorer_probs,
                          FIFA_TEAM)

OUT_PATH = "../frontend/public/predictions.json"
# Vite copies public/ into dist/ only at BUILD time -- a deployed static site
# serves dist/, which would otherwise go stale between rebuilds even though
# this script re-ran. Writing to dist/ too (when it exists, i.e. already
# built at least once) keeps a live deployment fresh without a rebuild.
DIST_OUT_PATH = "../frontend/dist/predictions.json"

HELDOUT = [
    {"model": "Raw goals", "acc": 0.613, "logloss": 0.902},
    {"model": "xG-based", "acc": 0.677, "logloss": 0.883},
    {"model": "xG + time decay", "acc": 0.677, "logloss": 0.881},
    {"model": "xG/goals 50/50 blend", "acc": 0.710, "logloss": 0.831},
    {"model": "Market alone", "acc": 0.778, "logloss": 0.720},
    {"model": "Blend 25% model / 75% market", "acc": 0.815, "logloss": 0.749},
]


def american_to_prob(ml):
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def resolve_advance(mat, lam, mu):
    p_a = float(np.tril(mat, -1).sum())   # team-a (matrix rows) wins
    p_d = float(np.trace(mat))
    p_b = float(np.triu(mat, 1).sum())
    lam_et = lam * ET_MINUTES_FRACTION * ET_INTENSITY
    mu_et = mu * ET_MINUTES_FRACTION * ET_INTENSITY
    et_a = et_b = et_d = 0.0
    from scipy.stats import poisson
    for x in range(6):
        for y in range(6):
            p = poisson.pmf(x, lam_et) * poisson.pmf(y, mu_et)
            if x > y:
                et_a += p
            elif y > x:
                et_b += p
            else:
                et_d += p
    adv_a = p_a + p_d * (et_a + et_d * SHOOTOUT_ARG_WIN)
    adv_b = p_b + p_d * (et_b + et_d * (1 - SHOOTOUT_ARG_WIN))
    return p_a, p_d, p_b, adv_a, adv_b


def top_scorelines(mat, home_is_a, n=6):
    flat = sorted(((mat[x, y], x, y) for x in range(mat.shape[0]) for y in range(mat.shape[1])), reverse=True)
    out = []
    for p, x, y in flat[:n]:
        # matrix a=rows, b=cols. home orientation depends on home_is_a
        hs, as_ = (x, y) if home_is_a else (y, x)
        out.append({"score": f"{hs}-{as_}", "p": float(p)})
    return out


def predict_match(attack, defense, team_idx, home, away):
    """Returns prediction oriented to home/away (matrix internally a=away? we
    call score_matrix(home, away) so a=home)."""
    mat, lam_home, mu_away = score_matrix(attack, defense, team_idx, home, away)
    p_home, p_draw, p_away, adv_home, adv_away = resolve_advance(mat, lam_home, mu_away)
    return {
        "xg": {"home": round(lam_home, 2), "away": round(mu_away, 2)},
        "result90": {"home": round(p_home, 4), "draw": round(p_draw, 4), "away": round(p_away, 4)},
        "advance": {"home": round(adv_home, 4), "away": round(adv_away, 4)},
        "scorelines": top_scorelines(mat, home_is_a=True),
    }


def result_label(g1, g2):
    return "home" if g1 > g2 else ("draw" if g1 == g2 else "away")


def result_name(label, home, away):
    return {"home": home, "draw": "Draw", "away": away}[label]


def _fnum(value, digits=1):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def _int(value):
    if pd.isna(value):
        return None
    return int(value)


def _text(value):
    if pd.isna(value):
        return None
    return str(value)


def build():
    conn = db.connect()
    try:
        xg_df, _ = build_xg_match_table(conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
        elo_map = dict(zip(elo["team_name"], elo["elo"]))

        # same blend as the deployable model
        xg_df = xg_df.copy()
        xg_df["xg1"] = BLEND_ALPHA * xg_df["xg1"] + (1 - BLEND_ALPHA) * xg_df["g1"]
        xg_df["xg2"] = BLEND_ALPHA * xg_df["xg2"] + (1 - BLEND_ALPHA) * xg_df["g2"]
        attack, defense, team_idx = fit_all(xg_df, elo_map)

        # xG-vs-goals overperformance (from raw, pre-blend table) for the basis view
        raw_df, _ = build_xg_match_table(conn)
        player_xg = player_tournament_xg(conn)
        unavailable = unavailable_players(conn)
        pen_counts = penalty_takers_tournament(conn)
        team_stats_df = pd.read_sql("""
            SELECT team_name, count(*) AS matches,
                   avg(possession_pct) AS possession,
                   avg(total_shots) AS shots,
                   avg(won_corners) AS corners,
                   avg(fouls_committed) AS fouls,
                   avg(yellow_cards) AS yellows,
                   sum(red_cards) AS reds
            FROM espn_match_team_stats
            GROUP BY team_name
        """, conn)
        weather_df = pd.read_sql("""
            SELECT ground, match_date, kickoff_hour_local, temperature_c,
                   humidity_pct, precipitation_mm, wind_speed_kmh
            FROM match_weather
        """, conn)
        availability_df = pd.read_sql("""
            SELECT team, player_name, status, reason, match_context
            FROM player_availability
            ORDER BY team, player_name
        """, conn)
        h2h_df = pd.read_sql("""
            SELECT year, round, score_summary, winner, notes
            FROM h2h_history
            ORDER BY year
        """, conn)
        odds_snapshot_df = pd.read_sql("""
            SELECT team1, team2, match_date, bookmaker, market,
                   team1_odds, draw_odds, team2_odds, notes
            FROM match_odds_snapshot
            ORDER BY captured_at DESC
        """, conn)
        referee_df = pd.read_sql("""
            SELECT referee_name, matches_sampled, avg_yellow_per_match,
                   avg_red_per_match, notes
            FROM referee_tendency
            ORDER BY computed_at DESC
        """, conn)
        fifa_official_df = pd.read_sql("""
            SELECT i.fifa_match_id, i.match_date, i.home_team, i.away_team,
                   o.name, o.role, o.country
            FROM fifa_match_index i
            JOIN fifa_match_officials o ON o.fifa_match_id = i.fifa_match_id
            ORDER BY i.match_date DESC, i.fifa_match_id
        """, conn)
        fifa_lineup_df = pd.read_sql("""
            SELECT i.fifa_match_id, i.match_date, i.home_team, i.away_team,
                   l.team_name, l.player_name, l.shirt_number, l.position,
                   l.starter, l.captain, l.status
            FROM fifa_match_index i
            JOIN fifa_match_lineups l ON l.fifa_match_id = i.fifa_match_id
            ORDER BY i.match_date DESC, l.team_name, l.shirt_number NULLS LAST, l.player_name
        """, conn)
        projected_lineup_df = pd.read_sql("""
            SELECT team_name, player_name, shirt_number, position, starts,
                   appearances, confidence, source
            FROM projected_team_lineups
            ORDER BY team_name, starts DESC, appearances DESC, shirt_number NULLS LAST, player_name
        """, conn)
        availability_coverage_df = pd.read_sql("""
            SELECT team_name, player_count, special_status_count, source, computed_at
            FROM team_availability_coverage
        """, conn)
        attack_summary_df = pd.read_sql("""
            SELECT team_name, player_name, goals, shots, source
            FROM team_player_attack_summary
            ORDER BY team_name, goals DESC, shots DESC, player_name
        """, conn)
        results_df = pd.read_sql("""
            SELECT match_num, round, match_date, team1, team2,
                   COALESCE(score_et_team1, score_ft_team1) AS score1,
                   COALESCE(score_et_team2, score_ft_team2) AS score2,
                   score_pens_team1, score_pens_team2, ground, goals1, goals2
            FROM worldcup_matches
            WHERE score_ft_team1 IS NOT NULL
            ORDER BY match_date DESC, match_num DESC
        """, conn)
        bracket_df = pd.read_sql("""
            SELECT match_num, round, match_date, match_time, team1, team2,
                   score_ft_team1, score_ft_team2,
                   score_et_team1, score_et_team2,
                   score_pens_team1, score_pens_team2,
                   ground
            FROM worldcup_matches
            WHERE round IN ('Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final', 'Final')
            ORDER BY match_num
        """, conn)
        freshness_df = pd.read_sql("""
            SELECT source, max(run_at) AS last_run,
                   count(*) FILTER (WHERE status = 'error') AS errors,
                   count(*) AS runs
            FROM collection_log
            GROUP BY source
            ORDER BY source
        """, conn)
        collection_log_df = pd.read_sql("""
            SELECT source, endpoint, scope, status, detail, run_at
            FROM collection_log
            ORDER BY run_at DESC
        """, conn)
    finally:
        conn.close()

    def team_form(team):
        xg = goals = 0.0
        for r in raw_df.itertuples():
            if r.team1 == team:
                xg += r.xg1; goals += r.g1
            elif r.team2 == team:
                xg += r.xg2; goals += r.g2
        return {"xg": round(xg, 2), "goals": int(goals)}

    def strength(team):
        if team not in team_idx:
            return {"attack": None, "defense": None, "elo": float(elo_map.get(team, 1500))}
        i = team_idx[team]
        return {"attack": round(float(attack[i]), 3), "defense": round(float(defense[i]), 3),
                "elo": float(elo_map.get(team, 1500))}

    def scorers_for(team, exp_goals):
        rate_conn = db.connect()
        try:
            pen_rate = team_penalty_rate(rate_conn, team)
        finally:
            rate_conn.close()
        sub = scorer_probs(team, exp_goals, player_xg, unavailable, pen_counts, pen_rate)
        return [{"name": r.player_name.title(), "p": round(float(r.p_anytime), 3),
                 "xg": round(float(r.xg), 2), "goals": int(r.goals), "penTaker": bool(r.is_taker)}
                for r in sub.head(6).itertuples()]

    def _norm_name(value):
        import re
        import unicodedata
        value = (value or "").replace("&", "and").lower()
        value = "".join(
            ch for ch in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(ch)
        )
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    def _same_team(a, b):
        aliases = {
            "usa": {"united states", "united states of america"},
            "united states": {"usa"},
            "turkey": {"turkiye", "türkiye"},
            "turkiye": {"turkey", "türkiye"},
            "czech republic": {"czechia"},
            "czechia": {"czech republic"},
            "bosnia and herzegovina": {"bosnia herzegovina"},
            "bosnia herzegovina": {"bosnia and herzegovina"},
            "dr congo": {"congo dr", "democratic republic of the congo"},
            "congo dr": {"dr congo", "democratic republic of the congo"},
            "cote d ivoire": {"ivory coast"},
            "ivory coast": {"cote d ivoire"},
            "cabo verde": {"cape verde"},
            "cape verde": {"cabo verde"},
        }
        na, nb = _norm_name(a), _norm_name(b)
        return na == nb or nb in aliases.get(na, set()) or na in aliases.get(nb, set())

    def _matching_rows(df, col, team):
        if df.empty:
            return df
        mask = df[col].map(lambda value: _same_team(value, team))
        return df[mask]

    def team_stats(team):
        sub = _matching_rows(team_stats_df, "team_name", team)
        if sub.empty:
            return None
        r = sub.iloc[0]
        return {
            "matches": _int(r["matches"]),
            "possession": _fnum(r["possession"]),
            "shots": _fnum(r["shots"]),
            "corners": _fnum(r["corners"]),
            "fouls": _fnum(r["fouls"]),
            "yellows": _fnum(r["yellows"]),
            "reds": _int(r["reds"]),
        }

    def weather_for(ground, date):
        sub = weather_df[
            (weather_df["ground"] == ground)
            & (weather_df["match_date"].astype(str) == date)
        ]
        if sub.empty:
            return None
        r = sub.iloc[0]
        return {
            "ground": ground,
            "temperatureC": _fnum(r["temperature_c"]),
            "humidityPct": _int(r["humidity_pct"]),
            "precipitationMm": _fnum(r["precipitation_mm"]),
            "windKmh": _fnum(r["wind_speed_kmh"]),
        }

    def availability_for(*teams):
        sub = availability_df[availability_df["team"].isin(teams)]
        return [{
            "team": _text(r.team),
            "player": _text(r.player_name),
            "status": _text(r.status),
            "reason": _text(r.reason),
        } for r in sub.itertuples()]

    def availability_coverage_for(*teams):
        rows = []
        for team in teams:
            sub = _matching_rows(availability_coverage_df, "team_name", team)
            if sub.empty:
                continue
            r = sub.iloc[0]
            rows.append({
                "team": team,
                "playerCount": _int(r["player_count"]),
                "specialStatusCount": _int(r["special_status_count"]),
                "source": _text(r["source"]),
                "checkedAt": r["computed_at"].isoformat() if pd.notna(r["computed_at"]) else None,
                "note": "Official squad status checked; this is not a confirmed injury report.",
            })
        return rows

    def h2h_for(home, away):
        names = {home, away}
        rows = []
        for r in h2h_df.itertuples():
            if all(t in r.score_summary for t in names):
                rows.append({
                    "year": int(r.year),
                    "round": _text(r.round),
                    "score": _text(r.score_summary),
                    "winner": _text(r.winner),
                    "notes": _text(r.notes),
                })
        return rows

    def odds_for(home, away):
        sub = odds_snapshot_df[
            ((odds_snapshot_df["team1"] == home) & (odds_snapshot_df["team2"] == away))
            | ((odds_snapshot_df["team1"] == away) & (odds_snapshot_df["team2"] == home))
        ]
        rows = []
        for r in sub.itertuples():
            rows.append({
                "bookmaker": _text(r.bookmaker),
                "market": _text(r.market),
                "team1": _text(r.team1),
                "team2": _text(r.team2),
                "team1Odds": _text(r.team1_odds),
                "drawOdds": _text(r.draw_odds),
                "team2Odds": _text(r.team2_odds),
                "notes": _text(r.notes),
            })
        return rows

    def _same_pair(home, away, row_home, row_away):
        return (
            _same_team(home, row_home) and _same_team(away, row_away)
        ) or (
            _same_team(home, row_away) and _same_team(away, row_home)
        )

    def _tendency_for(referee_name):
        if referee_df.empty or not referee_name:
            return {}
        sub = referee_df[referee_df["referee_name"].map(_norm_name) == _norm_name(referee_name)]
        if sub.empty:
            return {}
        r = sub.iloc[0]
        return {
            "matchesSampled": _int(r["matches_sampled"]),
            "avgYellow": _fnum(r["avg_yellow_per_match"]),
            "avgRed": _fnum(r["avg_red_per_match"]),
            "notes": _text(r["notes"]),
        }

    def referee_for(home, away, date=None):
        if not fifa_official_df.empty:
            candidates = []
            for r in fifa_official_df.itertuples():
                if date and str(r.match_date) != date:
                    continue
                if not _same_pair(home, away, r.home_team, r.away_team):
                    continue
                role = _text(r.role) or ""
                role_l = role.lower()
                priority = 0 if role_l == "referee" else (1 if "referee" in role_l and "assistant" not in role_l else 2)
                candidates.append((priority, r))
            if candidates:
                _, r = sorted(candidates, key=lambda item: item[0])[0]
                tendency = _tendency_for(r.name)
                return {
                    "name": _text(r.name),
                    "role": _text(r.role),
                    "country": _text(r.country),
                    "source": "fifa_match_officials",
                    **tendency,
                }

        if {home, away} != {"England", "Argentina"} or referee_df.empty:
            return None
        r = referee_df.iloc[0]
        return {
            "name": _text(r["referee_name"]),
            "role": "Referee tendency prior",
            "source": "referee_tendency",
            "matchesSampled": _int(r["matches_sampled"]),
            "avgYellow": _fnum(r["avg_yellow_per_match"]),
            "avgRed": _fnum(r["avg_red_per_match"]),
            "notes": _text(r["notes"]),
        }

    def lineups_for(home, away, date=None):
        source = "fifa_match_lineups"
        rows = {"home": [], "away": []}
        if not fifa_lineup_df.empty:
            for r in fifa_lineup_df.itertuples():
                if date and str(r.match_date) != date:
                    continue
                if not _same_pair(home, away, r.home_team, r.away_team):
                    continue
                side = "home" if _same_team(r.team_name, home) else ("away" if _same_team(r.team_name, away) else None)
                if not side:
                    continue
                rows[side].append({
                    "team": _text(r.team_name),
                    "player": _text(r.player_name),
                    "shirtNumber": _int(r.shirt_number),
                    "position": _int(r.position),
                    "starter": None if pd.isna(r.starter) else bool(r.starter),
                    "captain": None if pd.isna(r.captain) else bool(r.captain),
                    "status": _text(r.status),
                    "source": source,
                })
        if rows["home"] and rows["away"]:
            return {**rows, "source": source}

        source = "projected_team_lineups"
        for side, team in (("home", home), ("away", away)):
            sub = _matching_rows(projected_lineup_df, "team_name", team).head(11)
            rows[side] = [{
                "team": team,
                "player": _text(r.player_name),
                "shirtNumber": _int(r.shirt_number),
                "position": _int(r.position),
                "starter": True,
                "captain": None,
                "status": "projected",
                "confidence": _fnum(r.confidence, 3),
                "source": _text(r.source),
            } for r in sub.itertuples()]
        return {**rows, "source": source}

    def route_for(team, n=5):
        rows = []
        sub = results_df[(results_df["team1"] == team) | (results_df["team2"] == team)].head(n)
        for r in sub.itertuples():
            is_team1 = r.team1 == team
            gf = int(r.score1 if is_team1 else r.score2)
            ga = int(r.score2 if is_team1 else r.score1)
            opp = r.team2 if is_team1 else r.team1
            if gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "D"
            rows.append({
                "round": _text(r.round),
                "date": str(r.match_date),
                "opponent": _text(opp),
                "score": f"{gf}-{ga}",
                "result": result,
                "ground": _text(r.ground),
            })
        return rows

    def top_scorers(n=8):
        counts = Counter()
        teams = {}
        for r in results_df.itertuples():
            for team, goals in ((r.team1, r.goals1 or []), (r.team2, r.goals2 or [])):
                for goal in goals:
                    name = goal.get("name")
                    if name:
                        counts[name] += 1
                        teams[name] = team
        return [{"name": name, "team": teams.get(name), "goals": goals}
                for name, goals in counts.most_common(n)]

    def team_scorers(team, n=5):
        counts = Counter()
        for r in results_df.itertuples():
            for side_team, goals in ((r.team1, r.goals1 or []), (r.team2, r.goals2 or [])):
                if side_team != team:
                    continue
                for goal in goals:
                    name = goal.get("name")
                    if name:
                        counts[name] += 1
        if counts:
            return [{"name": name, "goals": goals, "source": "worldcup_goals"} for name, goals in counts.most_common(n)]
        sub = _matching_rows(attack_summary_df, "team_name", team).head(n)
        return [{
            "name": _text(r.player_name),
            "goals": _int(r.goals) or 0,
            "shots": _int(r.shots) or 0,
            "source": _text(r.source),
            "note": "Fallback top attackers by FIFA shot events; team has no recorded scorer.",
        } for r in sub.itertuples()]

    def team_record(team):
        wins = draws = losses = gf = ga = played = 0
        for r in results_df.itertuples():
            if r.team1 != team and r.team2 != team:
                continue
            played += 1
            is_team1 = r.team1 == team
            score_for = int(r.score1 if is_team1 else r.score2)
            score_against = int(r.score2 if is_team1 else r.score1)
            gf += score_for
            ga += score_against
            if score_for > score_against:
                wins += 1
            elif score_for < score_against:
                losses += 1
            else:
                draws += 1
        return {
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goalsFor": gf,
            "goalsAgainst": ga,
            "goalDiff": gf - ga,
        }

    def teams():
        names = sorted(
            set(results_df["team1"].dropna())
            | set(results_df["team2"].dropna())
            | set(bracket_df["team1"].dropna())
            | set(bracket_df["team2"].dropna())
        )
        out = []
        for name in names:
            if name.startswith(("W", "L")) and name[1:].isdigit():
                continue
            form = team_form(name)
            record = team_record(name)
            out.append({
                "name": name,
                "strength": strength(name),
                "form": form,
                "goalsMinusXg": round(form["goals"] - form["xg"], 2),
                "record": record,
                "teamStats": team_stats(name),
                "route": route_for(name, 8),
                "topScorers": team_scorers(name),
                "availability": availability_for(name),
                "availabilityCoverage": availability_coverage_for(name)[0] if availability_coverage_for(name) else None,
            })
        out.sort(key=lambda row: (
            row["record"]["wins"],
            row["record"]["goalDiff"],
            row["form"]["xg"],
        ), reverse=True)
        return out

    def freshness():
        rows = []
        for r in freshness_df.itertuples():
            rows.append({
                "source": r.source,
                "lastRun": r.last_run.isoformat() if pd.notna(r.last_run) else None,
                "runs": int(r.runs),
                "errors": int(r.errors),
            })
        return rows

    def source_details():
        out = {}
        for source, group in collection_log_df.groupby("source", sort=True):
            status_counts = group["status"].value_counts().to_dict()
            endpoints = sorted(set(group["endpoint"].dropna().astype(str)))
            recent = []
            for r in group.head(30).itertuples():
                recent.append({
                    "endpoint": _text(r.endpoint),
                    "scope": _text(r.scope),
                    "status": _text(r.status),
                    "detail": _text(r.detail),
                    "runAt": r.run_at.isoformat() if pd.notna(r.run_at) else None,
                })
            out[str(source)] = {
                "endpoints": endpoints,
                "statusCounts": {str(k): int(v) for k, v in status_counts.items()},
                "recentLogs": recent,
            }
        return out

    def _time_et(value):
        if pd.isna(value):
            return None
        if hasattr(value, "strftime"):
            return f"{value.strftime('%H:%M')} ET"
        value = str(value)
        return f"{value[:5]} ET" if len(value) >= 5 else value

    def bracket_winner(row):
        if pd.isna(row.score_ft_team1) or pd.isna(row.score_ft_team2):
            return None

        home_score = row.score_et_team1 if pd.notna(row.score_et_team1) else row.score_ft_team1
        away_score = row.score_et_team2 if pd.notna(row.score_et_team2) else row.score_ft_team2
        if home_score > away_score:
            return "home"
        if away_score > home_score:
            return "away"
        if pd.notna(row.score_pens_team1) and pd.notna(row.score_pens_team2):
            if row.score_pens_team1 > row.score_pens_team2:
                return "home"
            if row.score_pens_team2 > row.score_pens_team1:
                return "away"
        return None

    def bracket_period(row):
        if pd.isna(row.score_ft_team1) or pd.isna(row.score_ft_team2):
            return "UPCOMING"
        if pd.notna(row.score_pens_team1) and pd.notna(row.score_pens_team2):
            return "FT (P)"
        if pd.notna(row.score_et_team1) and pd.notna(row.score_et_team2):
            return "AET"
        return "FT"

    def bracket_score_tied(score):
        home = score["homeEt"] if score["homeEt"] is not None else score["home"]
        away = score["awayEt"] if score["awayEt"] is not None else score["away"]
        return home is not None and away is not None and home == away

    def bracket():
        rounds = ["Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final"]
        matches = []
        for r in bracket_df.itertuples():
            winner = bracket_winner(r)
            matches.append({
                "matchNum": int(r.match_num),
                "round": _text(r.round),
                "date": str(r.match_date),
                "time": _time_et(r.match_time),
                "ground": _text(r.ground),
                "home": _text(r.team1),
                "away": _text(r.team2),
                "status": "finished" if pd.notna(r.score_ft_team1) and pd.notna(r.score_ft_team2) else "upcoming",
                "period": bracket_period(r),
                "winner": winner,
                "winnerName": _text(r.team1 if winner == "home" else r.team2) if winner else None,
                "score": {
                    "home": _int(r.score_ft_team1),
                    "away": _int(r.score_ft_team2),
                    "homeEt": _int(r.score_et_team1),
                    "awayEt": _int(r.score_et_team2),
                    "homePens": _int(r.score_pens_team1),
                    "awayPens": _int(r.score_pens_team2),
                },
            })
        for i, round_name in enumerate(rounds[:-1]):
            next_teams = {
                team
                for m in matches
                if m["round"] == rounds[i + 1]
                for team in (m["home"], m["away"])
                if team
            }
            for m in matches:
                if m["round"] != round_name or m["winner"] or m["status"] != "finished":
                    continue
                if m["home"] in next_teams and m["away"] not in next_teams:
                    m["winner"] = "home"
                    m["winnerName"] = m["home"]
                elif m["away"] in next_teams and m["home"] not in next_teams:
                    m["winner"] = "away"
                    m["winnerName"] = m["away"]
                if m["winner"] and bracket_score_tied(m["score"]):
                    m["period"] = "FT (P)"
        return {
            "rounds": rounds,
            "matches": matches,
        }

    def historical_evaluation():
        df = raw_df.copy()
        df["xg1"] = BLEND_ALPHA * df["xg1"] + (1 - BLEND_ALPHA) * df["g1"]
        df["xg2"] = BLEND_ALPHA * df["xg2"] + (1 - BLEND_ALPHA) * df["g2"]

        train = df[df["date"] < KNOCKOUT_START].copy()
        test = df[df["date"] >= KNOCKOUT_START].copy()
        teams = sorted(set(train["team1"]) | set(train["team2"]))
        team_idx_eval = {t: i for i, t in enumerate(teams)}

        counts = {}
        for r in train.itertuples():
            counts[r.team1] = counts.get(r.team1, 0) + 1
            counts[r.team2] = counts.get(r.team2, 0) + 1

        latest = train["date"].max()
        weights = np.array([0.5 ** ((latest - d).days / 20.0) for d in train["date"]])
        eval_attack, eval_defense = fit(train, team_idx_eval, len(teams), ("xg1", "xg2"), weights)
        eval_attack, eval_defense = shrink(eval_attack, eval_defense, teams, counts, elo_map)

        meta = {}
        meta_by_pair_score = {}
        for r in results_df.itertuples():
            key = (str(r.match_date), frozenset([r.team1, r.team2]))
            meta[key] = r
            score_key = (frozenset([r.team1, r.team2]), frozenset([int(r.score1), int(r.score2)]))
            meta_by_pair_score[score_key] = r

        rows = []
        correct = 0
        log_loss = 0.0
        for r in test.itertuples():
            if r.team1 not in team_idx_eval or r.team2 not in team_idx_eval:
                continue
            ph, pdw, pa = predict_result_probs(eval_attack, eval_defense, team_idx_eval, r.team1, r.team2)
            probs = {"home": ph, "draw": pdw, "away": pa}
            actual = result_label(r.g1, r.g2)
            predicted = max(probs.items(), key=lambda item: item[1])[0]
            is_correct = predicted == actual
            correct += int(is_correct)
            log_loss += -np.log(max(probs[actual], 1e-10))
            match_meta = meta.get((r.date.strftime("%Y-%m-%d"), frozenset([r.team1, r.team2])))
            if match_meta is None:
                match_meta = meta_by_pair_score.get((
                    frozenset([r.team1, r.team2]),
                    frozenset([int(r.g1), int(r.g2)]),
                ))
            rows.append({
                "date": r.date.strftime("%Y-%m-%d"),
                "round": _text(match_meta.round) if match_meta is not None else None,
                "ground": _text(match_meta.ground) if match_meta is not None else None,
                "home": r.team1,
                "away": r.team2,
                "actualScore": f"{int(r.g1)}-{int(r.g2)}",
                "actual": actual,
                "actualName": result_name(actual, r.team1, r.team2),
                "predicted": predicted,
                "predictedName": result_name(predicted, r.team1, r.team2),
                "correct": bool(is_correct),
                "probabilities": {
                    "home": round(float(ph), 4),
                    "draw": round(float(pdw), 4),
                    "away": round(float(pa), 4),
                },
                "actualProbability": round(float(probs[actual]), 4),
                "logLoss": round(float(-np.log(max(probs[actual], 1e-10))), 4),
            })

        n = len(rows)
        return {
            "method": "Held-out backtest: train before the split date, test on later finished matches.",
            "splitDate": KNOCKOUT_START.strftime("%Y-%m-%d"),
            "total": n,
            "correct": correct,
            "accuracy": round(correct / n, 4) if n else None,
            "avgLogLoss": round(log_loss / n, 4) if n else None,
            "matches": rows,
        }

    def enrich(home, away, ground, date):
        return {
            "weather": weather_for(ground, date),
            "teamStats": {"home": team_stats(home), "away": team_stats(away)},
            "availability": availability_for(home, away),
            "availabilityCoverage": availability_coverage_for(home, away),
            "lineups": lineups_for(home, away, date),
            "h2h": h2h_for(home, away),
            "odds": odds_for(home, away),
            "referee": referee_for(home, away, date),
            "route": {"home": route_for(home), "away": route_for(away)},
        }

    # --- hero match: England (home) vs Argentina (away) ---
    eng_arg = predict_match(attack, defense, team_idx, "England", "Argentina")
    m_eng, m_draw, m_arg = (american_to_prob(175), american_to_prob(180), american_to_prob(200))
    s = m_eng + m_draw + m_arg
    market = {"home": round(m_eng / s, 4), "draw": round(m_draw / s, 4), "away": round(m_arg / s, 4)}
    w = 0.25
    blend = {k: round(w * eng_arg["result90"][k] + (1 - w) * market[k], 4)
             for k in ("home", "draw", "away")}

    matches = [{
        "id": "eng-arg-sf",
        "round": "Semi-final", "date": "2026-07-15", "time": "15:00 ET",
        "venue": "Mercedes-Benz Stadium, Atlanta", "ground": "Atlanta",
        "home": "England", "away": "Argentina", "status": "upcoming",
        "prediction": {**eng_arg, "market": market, "blend": blend,
                       "scorers": {"home": scorers_for("England", eng_arg["xg"]["home"]),
                                   "away": scorers_for("Argentina", eng_arg["xg"]["away"])}},
        "basis": {
            "strength": {"home": strength("England"), "away": strength("Argentina")},
            "form": {"home": team_form("England"), "away": team_form("Argentina")},
            "notes": [
                "Model input is a 50/50 blend of xG and actual goals (held-out validated).",
                "Argentina scored 17 goals from only 11.25 xG (+5.75) -- partly unsustainable finishing.",
                "England created more total xG (11.94) than Argentina despite fewer goals.",
                "Final number blends 25% model / 75% market; the market is the stronger signal.",
            ],
        },
        "intelligence": enrich("England", "Argentina", "Atlanta", "2026-07-15"),
    }]

    # --- final scenarios: Spain vs each possible finalist ---
    for opp in ("England", "Argentina"):
        pm = predict_match(attack, defense, team_idx, "Spain", opp)
        matches.append({
            "id": f"final-spain-{opp.lower()}",
            "round": "Final (scenario)", "date": "2026-07-19", "time": "15:00 ET",
            "venue": "MetLife Stadium, New York/New Jersey",
            "ground": "New York/New Jersey (East Rutherford)",
            "home": "Spain", "away": opp, "status": "scenario",
            "prediction": {**pm,
                           "scorers": {"home": scorers_for("Spain", pm["xg"]["home"]),
                                       "away": scorers_for(opp, pm["xg"]["away"])}},
            "basis": {
                "strength": {"home": strength("Spain"), "away": strength(opp)},
                "form": {"home": team_form("Spain"), "away": team_form(opp)},
                "notes": [f"Conditional on {opp} winning the semi-final.",
                          "Spain is the tournament's #1 Elo side and beat France 2-0 in the semi."],
            },
            "intelligence": enrich("Spain", opp, "New York/New Jersey (East Rutherford)", "2026-07-19"),
        })

    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": {
            "name": "xG/goals Dixon-Coles + market blend",
            "heldout": HELDOUT,
        },
        "tournament": {
            "topScorers": top_scorers(),
            "teams": teams(),
        },
        "dataFreshness": freshness(),
        "sourceDetails": source_details(),
        "history": {
            "evaluation": historical_evaluation(),
        },
        "bracket": bracket(),
        "matches": matches,
    }

    import os
    payload = json.dumps(out, indent=2, allow_nan=False)

    targets = [OUT_PATH]
    if os.path.exists(os.path.dirname(DIST_OUT_PATH)):
        targets.append(DIST_OUT_PATH)  # only if a build already exists

    for path in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # atomic write: a cron run landing mid-request must never serve a
        # half-written JSON file to the frontend.
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w") as f:
            f.write(payload)
        os.replace(tmp_path, path)
        print(f"Wrote {path} with {len(matches)} matches")


if __name__ == "__main__":
    build()
