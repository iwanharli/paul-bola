"""Thin client for TheStatsAPI (https://api.thestatsapi.com)."""
import os
import time

import requests

BASE_URL = os.environ.get("STATSAPI_BASE_URL", "https://api.thestatsapi.com/api")
API_KEY = os.environ.get("STATSAPI_KEY")

if not API_KEY:
    raise RuntimeError("STATSAPI_KEY is not set (check your .env file)")


class StatsAPIClient:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY, rate_limit_sleep: float = 0.3):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.rate_limit_sleep = rate_limit_sleep

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        time.sleep(self.rate_limit_sleep)
        return resp.json()

    def paginate(self, path: str, params: dict | None = None, per_page: int = 100):
        """Yield every item across all pages of a paginated endpoint."""
        params = dict(params or {})
        params["per_page"] = per_page
        page = 1
        while True:
            params["page"] = page
            payload = self._get(path, params)
            items = payload.get("data", [])
            for item in items:
                yield item
            meta = payload.get("meta", {})
            total_pages = meta.get("total_pages") or meta.get("last_page")
            if not items or (total_pages and page >= total_pages):
                break
            page += 1

    # --- Competitions ---
    def list_competitions(self, country: str | None = None, comp_type: str | None = None):
        params = {}
        if country:
            params["country"] = country
        if comp_type:
            params["type"] = comp_type
        yield from self.paginate("/football/competitions", params)

    def get_competition(self, competition_id: int) -> dict:
        return self._get(f"/football/competitions/{competition_id}")

    def list_seasons(self, competition_id: int):
        return self._get(f"/football/competitions/{competition_id}/seasons").get("data", [])

    # --- Matches ---
    def list_matches(self, competition_id: int | None = None, date_from: str | None = None,
                      date_to: str | None = None, status: str | None = None,
                      stage: str | None = None, matchday: int | None = None):
        params = {}
        if competition_id:
            params["competition"] = competition_id
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if status:
            params["status"] = status
        if stage:
            params["stage"] = stage
        if matchday:
            params["matchday"] = matchday
        yield from self.paginate("/football/matches", params)

    def get_match(self, match_id: int) -> dict:
        return self._get(f"/football/matches/{match_id}").get("data", {})

    def get_match_stats(self, match_id: int) -> dict:
        return self._get(f"/football/matches/{match_id}/stats").get("data", {})

    def get_match_player_stats(self, match_id: int):
        return self._get(f"/football/matches/{match_id}/player-stats").get("data", [])

    def get_match_shotmap(self, match_id: int):
        return self._get(f"/football/matches/{match_id}/shotmap").get("data", [])

    # --- Teams ---
    def get_team(self, team_id: int) -> dict:
        return self._get(f"/football/teams/{team_id}").get("data", {})

    def get_team_players(self, team_id: int):
        return self._get(f"/football/teams/{team_id}/players").get("data", [])

    # --- Coverage (useful to check before bulk-pulling a competition) ---
    def get_coverage(self, competition_id: int) -> dict:
        return self._get(f"/coverage/leagues/{competition_id}")
