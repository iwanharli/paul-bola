"""
Central competition config.

Everything competition-specific (API ids, source URLs, league paths) lives
here so adding a new competition is one registry entry -- not edits scattered
across a dozen collectors and the model. Select which competition is active
with the COMPETITION env var (default: wc2026).

    COMPETITION=euro2028 python orchestrate.py

NOTE: this centralizes the *data plumbing*. The forecast layer
(export_predictions.py) still has competition-specific matchups/venues; those
are a separate generalization step. This refactor is the foundation for it.
"""
import os

COMPETITIONS = {
    "wc2026": {
        "name": "FIFA World Cup 2026",
        "fifa_competition_id": 17,
        "fifa_season_id": 285023,
        "espn_league": "fifa.world",
        "openfootball_url": (
            "https://raw.githubusercontent.com/openfootball/worldcup.json"
            "/master/2026/worldcup.json"
        ),
        "odds_api_sport_keys": ["soccer_fifa_world_cup", "soccer_international"],
    },
    # Template for a future competition -- fill the ids/paths and select via
    # COMPETITION=euro2028. Left here as a documented example, not active.
    # "euro2028": {
    #     "name": "UEFA Euro 2028",
    #     "fifa_competition_id": None,          # Euro isn't on the FIFA API
    #     "fifa_season_id": None,
    #     "espn_league": "uefa.euro",
    #     "openfootball_url": ".../2028/euro.json",
    #     "odds_api_sport_keys": ["soccer_uefa_european_championship"],
    # },
}

ACTIVE = os.environ.get("COMPETITION", "wc2026")
if ACTIVE not in COMPETITIONS:
    raise RuntimeError(
        f"Unknown COMPETITION={ACTIVE!r}. Known: {', '.join(COMPETITIONS)}"
    )

CONFIG = COMPETITIONS[ACTIVE]

# --- convenience accessors (import these) ---
NAME = CONFIG["name"]
FIFA_COMPETITION_ID = CONFIG["fifa_competition_id"]
FIFA_SEASON_ID = CONFIG["fifa_season_id"]
ESPN_LEAGUE = CONFIG["espn_league"]
ESPN_BASE = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LEAGUE}"
OPENFOOTBALL_URL = CONFIG["openfootball_url"]
ODDS_API_SPORT_KEYS = CONFIG["odds_api_sport_keys"]
