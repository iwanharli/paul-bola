"""Shared helpers for optional external-data collectors."""
import datetime as _dt
import re
import unicodedata


TEAM_ALIASES = {
    "USA": {"United States", "United States of America", "USMNT"},
    "DR Congo": {"Congo DR", "Congo Democratic Republic", "Democratic Republic of the Congo"},
    "Congo DR": {"DR Congo", "Democratic Republic of the Congo"},
    "Côte d'Ivoire": {"Ivory Coast", "Cote d'Ivoire"},
    "Ivory Coast": {"Côte d'Ivoire", "Cote d'Ivoire"},
    "Cape Verde": {"Cabo Verde"},
    "Cabo Verde": {"Cape Verde"},
    "Bosnia & Herzegovina": {"Bosnia and Herzegovina"},
    "Bosnia and Herzegovina": {"Bosnia & Herzegovina"},
}


def normalize_name(value: str | None) -> str:
    value = value or ""
    value = value.replace("&", "and")
    value = "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )
    value = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def team_names_match(a: str | None, b: str | None) -> bool:
    if normalize_name(a) == normalize_name(b):
        return True
    aliases = TEAM_ALIASES.get(a or "", set()) | TEAM_ALIASES.get(b or "", set())
    return any(normalize_name(alias) in {normalize_name(a), normalize_name(b)} for alias in aliases)


def pair_matches(home_a: str | None, away_a: str | None, home_b: str | None, away_b: str | None) -> bool:
    return (
        team_names_match(home_a, home_b) and team_names_match(away_a, away_b)
    ) or (
        team_names_match(home_a, away_b) and team_names_match(away_a, home_b)
    )


def parse_date(value):
    if not value:
        return None
    if isinstance(value, _dt.date):
        return value
    text = str(value)
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return _dt.date.fromisoformat(text[:10])


def iso_date(value):
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def american_price(value):
    if value is None:
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value)
    return f"+{number}" if number > 0 else str(number)
