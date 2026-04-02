import os
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


FRANCE_TRAVAIL_CLIENT_ID: str = _require("FRANCE_TRAVAIL_CLIENT_ID")
FRANCE_TRAVAIL_CLIENT_SECRET: str = _require("FRANCE_TRAVAIL_CLIENT_SECRET")

def _parse_keywords(raw: str) -> list[str]:
    return [kw.strip() for kw in raw.split(",") if kw.strip()]


DEFAULT_KEYWORDS: list[str] = _parse_keywords(
    os.getenv("DEFAULT_KEYWORDS", "ingénieur télécom")
)
DEFAULT_LOCATION: str = os.getenv("DEFAULT_LOCATION", "75")
DEFAULT_MAX_RESULTS: int = int(os.getenv("DEFAULT_MAX_RESULTS", "50"))

SALARY_MIN: float = float(os.getenv("SALARY_MIN", "40000"))
REQUIRE_SALARY: bool = os.getenv("REQUIRE_SALARY", "false").lower() == "true"
VIE_ALLOWED_COUNTRIES: list[str] = ["japon", "japan", "états-unis", "etats-unis", "usa", "suisse", "switzerland"]
