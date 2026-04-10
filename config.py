import os

import yaml
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

# --- Secrets (from .env) ---

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


FRANCE_TRAVAIL_CLIENT_ID: str | None = os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
FRANCE_TRAVAIL_CLIENT_SECRET: str | None = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")

# --- User profile (from profile.yml) ---

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "profile.yml")
_EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "profile.example.yml")


def _load_profile() -> dict:
    path = _PROFILE_PATH if os.path.exists(_PROFILE_PATH) else _EXAMPLE_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_profile = _load_profile()

DEFAULT_KEYWORDS: list[str] = _profile["search"]["keywords"]
DEFAULT_LOCATION: str = str(_profile["search"]["location"])
DEFAULT_MAX_RESULTS: int = int(_profile["search"]["max_results"])

SALARY_MIN: float = float(_profile["filters"]["salary"]["min"])
REQUIRE_SALARY: bool = bool(_profile["filters"]["salary"]["require"])
VIE_ALLOWED_COUNTRIES: list[str] = _profile["filters"]["vie_allowed_countries"]
TITLE_DOMAIN_KEYWORDS: list[str] = _profile["filters"].get("title_domain", [])
TITLE_EXCLUDE_PATTERNS: list[str] = _profile["filters"].get("title_exclude", [])

_scoring = _profile.get("scoring", {})
SCORING_PREFERRED_KEYWORDS: list[str] = _scoring.get("preferred_keywords", [])
SCORING_PREFERRED_REMOTE: str | None = _scoring.get("preferred_remote", None)
SCORING_TARGET_SALARY: float = float(_scoring.get("target_salary", SALARY_MIN))
