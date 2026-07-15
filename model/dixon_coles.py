"""
Dixon-Coles model for FIFA World Cup 2026, fit on all 101 finished matches
in db_boforecasting, used to predict the England vs Argentina semifinal.

Method:
  - Each team gets an attack and defense strength parameter, fit by maximum
    likelihood on full-time (90-min) goals across every finished match --
    not just Argentina/England's own 6 games, so the small-sample problem
    flagged earlier is mitigated by pooling information across the whole
    tournament (via the shared home-advantage/rho parameters and the sheer
    number of opponents each team's strength is measured against).
  - Includes the classic Dixon-Coles low-score correlation adjustment (rho)
    for 0-0/1-0/0-1/1-1, since plain independent Poisson underrates draws.
  - A small home-advantage term applies only to host-nation matches
    (Mexico/USA/Canada) -- everyone else plays at a neutral US/Mexico/Canada
    venue this tournament.
  - Teams with very few matches (early group-stage exits) get their attack/
    defense shrunk toward a prior derived from Elo rating, since 2-3 matches
    alone is too noisy to trust -- this directly addresses the "opponent-
    strength" and "small sample" weaknesses identified earlier.

Caveat (explicit, not hidden): full-time score is the actual match outcome,
not an xG-based rate -- goals are a noisy, low-count signal (most matches
0-3 total goals). This model captures real scoring tendency, but with wide
uncertainty on any single match. Treat its outputs as calibrated
probabilities, not certainties.

Usage:
    python dixon_coles.py
"""
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

sys.path.insert(0, "../collector")
from dotenv import load_dotenv

load_dotenv()
import db

HOST_NATIONS = {"Mexico", "USA", "Canada"}
ELO_PRIOR_WEIGHT = 3.0  # in "pseudo-matches" -- shrinkage strength for thin-sample teams


def load_matches():
    conn = db.connect()
    try:
        df = pd.read_sql("""
            SELECT team1, team2, score_ft_team1 AS g1, score_ft_team2 AS g2, ground
            FROM worldcup_matches
            WHERE score_ft_team1 IS NOT NULL AND score_ft_team2 IS NOT NULL
        """, conn)
        elo = pd.read_sql("SELECT team_name, elo FROM team_elo_ratings", conn)
    finally:
        conn.close()
    df["is_host_home"] = df["team1"].isin(HOST_NATIONS)
    return df, elo


def build_team_index(df):
    teams = sorted(set(df["team1"]) | set(df["team2"]))
    return {t: i for i, t in enumerate(teams)}, teams


def tau(x, y, lam, mu, rho):
    """Dixon-Coles low-score adjustment factor."""
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    elif x == 0 and y == 1:
        return 1 + lam * rho
    elif x == 1 and y == 0:
        return 1 + mu * rho
    elif x == 1 and y == 1:
        return 1 - rho
    return 1.0


FIXED_RHO = -0.13  # Dixon & Coles (1997) reported ~-0.13 on English league data.
# Our own 101-match MLE for rho kept climbing to whatever bound we set
# (-0.3, -0.6, -0.95 all got hit exactly) instead of settling at an interior
# optimum -- a sign this small, knockout-heavy sample (lots of 1-1/0-0 draws
# before extra time) doesn't identify rho reliably, not that the true value
# is extreme. Estimating a parameter from data that can't identify it would
# just be overfitting dressed up as precision, so rho is fixed at the
# published literature value instead of fit here.


def negative_log_likelihood(params, df, team_idx, n_teams):
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    home_adv = params[2 * n_teams]
    rho = FIXED_RHO

    ll = 0.0
    for row in df.itertuples():
        i, j = team_idx[row.team1], team_idx[row.team2]
        home_bonus = home_adv if row.is_host_home else 0.0
        lam = np.exp(attack[i] - defense[j] + home_bonus)
        mu = np.exp(attack[j] - defense[i])
        g1, g2 = int(row.g1), int(row.g2)

        p = poisson.pmf(g1, lam) * poisson.pmf(g2, mu) * tau(g1, g2, lam, mu, rho)
        p = max(p, 1e-10)
        ll += np.log(p)
    return -ll


def fit_model(df, team_idx, n_teams):
    x0 = np.concatenate([np.zeros(n_teams), np.zeros(n_teams), [0.1, 0.0]])
    result = minimize(
        negative_log_likelihood, x0, args=(df, team_idx, n_teams),
        method="L-BFGS-B",
        bounds=[(-3, 3)] * n_teams + [(-3, 3)] * n_teams + [(-2, 2), (0, 0)],  # rho fixed, see FIXED_RHO
    )
    return result


def shrink_toward_elo(attack, defense, teams, match_counts, elo_map):
    """Blend thin-sample teams' fitted strength toward an Elo-derived prior."""
    elo_values = np.array([elo_map.get(t, 1500) for t in teams])
    elo_z = (elo_values - elo_values.mean()) / elo_values.std()
    # Elo-implied attack prior: higher Elo -> more attack, less defense needed (scaled heuristically)
    prior_attack = elo_z * 0.3
    prior_defense = -elo_z * 0.3

    shrunk_attack = attack.copy()
    shrunk_defense = defense.copy()
    for i, t in enumerate(teams):
        n = match_counts.get(t, 0)
        w = n / (n + ELO_PRIOR_WEIGHT)  # weight on fitted data vs prior
        shrunk_attack[i] = w * attack[i] + (1 - w) * prior_attack[i]
        shrunk_defense[i] = w * defense[i] + (1 - w) * prior_defense[i]
    return shrunk_attack, shrunk_defense


def score_matrix(attack, defense, team_idx, teams, home_adv, rho, team_a, team_b, max_goals=8):
    i, j = team_idx[team_a], team_idx[team_b]
    lam = np.exp(attack[i] - defense[j])  # neutral venue -- no home_adv for this semifinal
    mu = np.exp(attack[j] - defense[i])

    mat = np.zeros((max_goals + 1, max_goals + 1))
    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            mat[x, y] = poisson.pmf(x, lam) * poisson.pmf(y, mu) * tau(x, y, lam, mu, rho)
    mat /= mat.sum()
    return mat, lam, mu


def main():
    df, elo = load_matches()
    team_idx, teams = build_team_index(df)
    n_teams = len(teams)
    elo_map = dict(zip(elo["team_name"], elo["elo"]))

    match_counts = {}
    for row in df.itertuples():
        match_counts[row.team1] = match_counts.get(row.team1, 0) + 1
        match_counts[row.team2] = match_counts.get(row.team2, 0) + 1

    print(f"Fitting Dixon-Coles on {len(df)} matches, {n_teams} teams...")
    result = fit_model(df, team_idx, n_teams)
    params = result.x
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    home_adv = params[2 * n_teams]
    rho = FIXED_RHO
    print(f"Converged: {result.success}, home_adv={home_adv:.3f}, rho={rho:.3f} (fixed, not fit)")

    # normalize attack to mean 0 for interpretability
    attack = attack - attack.mean()

    attack, defense = shrink_toward_elo(attack, defense, teams, match_counts, elo_map)

    print("\n=== Attack/Defense strength (post Elo-shrinkage), Argentina & England ===")
    for t in ["Argentina", "England"]:
        i = team_idx[t]
        print(f"{t}: attack={attack[i]:.3f}, defense={defense[i]:.3f}, "
              f"matches_played={match_counts.get(t)}, elo={elo_map.get(t)}")

    mat, lam, mu = score_matrix(attack, defense, team_idx, teams, home_adv, rho, "Argentina", "England")
    print(f"\nExpected goals (90 min): Argentina={lam:.2f}, England={mu:.2f}")

    p_arg_win = np.tril(mat, -1).sum()
    p_draw = np.trace(mat)
    p_eng_win = np.triu(mat, 1).sum()
    print(f"\n90-min result: Argentina {p_arg_win:.1%} | Draw {p_draw:.1%} | England {p_eng_win:.1%}")

    print("\nTop 8 most likely scorelines (90 min):")
    flat = [((x, y), mat[x, y]) for x in range(mat.shape[0]) for y in range(mat.shape[1])]
    flat.sort(key=lambda t: -t[1])
    for (x, y), p in flat[:8]:
        print(f"  Argentina {x}-{y} England: {p:.2%}")

    # Extra time / penalties for the draw slice: rough model -- ET adds a small
    # extra scoring window (~30 min = 1/3 of 90 min rate), then a coin-flip-ish
    # penalty shootout slightly favoring nothing (no real data to model pens).
    print("\n--- Knockout resolution (draw -> ET -> penalties) ---")
    lam_et, mu_et = lam / 3, mu / 3
    et_draw_given_draw = 0.0
    et_arg_given_draw = 0.0
    et_eng_given_draw = 0.0
    for x in range(4):
        for y in range(4):
            p = poisson.pmf(x, lam_et) * poisson.pmf(y, mu_et)
            if x > y:
                et_arg_given_draw += p
            elif y > x:
                et_eng_given_draw += p
            else:
                et_draw_given_draw += p
    p_arg_advance = p_arg_win + p_draw * (et_arg_given_draw + et_draw_given_draw * 0.5)
    p_eng_advance = p_eng_win + p_draw * (et_eng_given_draw + et_draw_given_draw * 0.5)
    print(f"P(Argentina advances) = {p_arg_advance:.1%}")
    print(f"P(England advances)   = {p_eng_advance:.1%}")

    backtest(df, attack, defense, team_idx, teams, home_adv, rho)

    return {
        "attack": dict(zip(teams, attack)),
        "defense": dict(zip(teams, defense)),
        "home_adv": home_adv,
        "rho": rho,
        "team_idx": team_idx,
        "teams": teams,
    }


def backtest(df, attack, defense, team_idx, teams, home_adv, rho):
    """
    Evaluate the fitted model against every match it was trained on.

    Caveat this doesn't hide: this is an IN-SAMPLE check (the model was fit
    on these same 101 matches), so it measures fit quality, not predictive
    accuracy on new matches. A true accuracy claim needs a held-out test
    (e.g. fit on group stage only, evaluate on knockout stage) -- flagged
    here rather than presented as if this were out-of-sample validation.
    """
    print("\n=== Backtest vs all 101 finished matches (IN-SAMPLE fit check) ===")
    correct_result = 0
    correct_score = 0
    log_loss_sum = 0.0
    n = len(df)

    for row in df.itertuples():
        i, j = team_idx[row.team1], team_idx[row.team2]
        home_bonus = home_adv if row.is_host_home else 0.0
        lam = np.exp(attack[i] - defense[j] + home_bonus)
        mu = np.exp(attack[j] - defense[i])
        g1, g2 = int(row.g1), int(row.g2)

        # most likely scoreline under this lam/mu
        best_score, best_p = None, -1
        p_home, p_draw, p_away = 0.0, 0.0, 0.0
        for x in range(7):
            for y in range(7):
                p = poisson.pmf(x, lam) * poisson.pmf(y, mu) * tau(x, y, lam, mu, rho)
                if x > y:
                    p_home += p
                elif x == y:
                    p_draw += p
                else:
                    p_away += p
                if p > best_p:
                    best_p, best_score = p, (x, y)

        actual_result = "home" if g1 > g2 else ("draw" if g1 == g2 else "away")
        predicted_result = max([("home", p_home), ("draw", p_draw), ("away", p_away)], key=lambda t: t[1])[0]
        if predicted_result == actual_result:
            correct_result += 1
        if best_score == (g1, g2):
            correct_score += 1

        actual_p = {"home": p_home, "draw": p_draw, "away": p_away}[actual_result]
        log_loss_sum += -np.log(max(actual_p, 1e-10))

    print(f"Result accuracy (W/D/L): {correct_result}/{n} = {correct_result / n:.1%}")
    print(f"Exact scoreline accuracy: {correct_score}/{n} = {correct_score / n:.1%}")
    print(f"Average log-loss: {log_loss_sum / n:.3f} (lower is better; ~1.0 ~ coin-flip-level uncertainty)")
    print("NOTE: this is in-sample -- the model saw these results while fitting. "
          "Treat this as a sanity check, not a claim of real predictive accuracy.")


if __name__ == "__main__":
    main()
