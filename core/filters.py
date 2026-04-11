import re
from datetime import datetime, timezone, timedelta

import config
from models import JobOffer

_MAX_AGE_DAYS = 14

# Contract type codes as returned by the FranceTravail API
_VIE_KEYWORDS = {"vie", "via", "volontariat international"}

# Compiled once from profile.yml at import time
_TITLE_EXCLUDE_RE = (
    re.compile(
        r"\b(" + "|".join(re.escape(p) for p in config.TITLE_EXCLUDE_PATTERNS) + r")\b",
        re.IGNORECASE,
    )
    if config.TITLE_EXCLUDE_PATTERNS else None
)

_TITLE_DOMAIN_RES = [
    re.compile(re.escape(kw), re.IGNORECASE)
    for kw in config.TITLE_DOMAIN_KEYWORDS
]


def _is_vie(contract_type: str) -> bool:
    ct = contract_type.lower()
    return any(kw in ct for kw in _VIE_KEYWORDS)


def _vie_country_allowed(offer: JobOffer) -> bool:
    location = (offer.location or "").lower()
    return any(country in location for country in config.VIE_ALLOWED_COUNTRIES)


def _contract_allowed(offer: JobOffer) -> bool:
    if not offer.contract_type:
        return False
    ct = offer.contract_type.lower()
    if "cdi" in ct:
        return True
    if "profession libérale" in ct or "profession liberale" in ct:
        return True
    if _is_vie(ct):
        return _vie_country_allowed(offer)
    return False


def _experience_allowed(offer: JobOffer) -> bool:
    if not offer.experience:
        return True
    exp = offer.experience.lower()
    if "débutant" in exp or "debutant" in exp:
        return True
    if "exig" in exp:
        return False
    if "mois" in exp:
        return True
    match = re.search(r"\d+", exp)
    if match:
        return int(match.group()) <= 2
    return True


def _parse_age_days(posted_at: str) -> int | None:
    """Return the age of the offer in days, or None if unparseable."""
    # ISO datetime from France Travail: "2026-03-28T12:00:00+02:00"
    try:
        dt = datetime.fromisoformat(posted_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except ValueError:
        pass
    # French relative string from WTTJ: "il y a 3 jours", "aujourd'hui", "il y a 2 semaines"
    s = posted_at.lower()
    if "aujourd" in s:
        return 0
    m = re.search(r"il y a\s+(\d+)\s+(jour|semaine|mois)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "jour":
            return n
        if unit == "semaine":
            return n * 7
        if unit == "mois":
            return n * 30
    return None


def _age_allowed(offer: JobOffer) -> bool:
    if not offer.posted_at:
        return True  # unknown date — keep
    age = _parse_age_days(offer.posted_at)
    if age is None:
        return True  # unparseable — keep
    return age <= _MAX_AGE_DAYS


def _salary_allowed(offer: JobOffer) -> bool:
    if offer.salary_min is None:
        return not config.REQUIRE_SALARY
    return offer.salary_min >= config.SALARY_MIN


def _title_domain_allowed(offer: JobOffer) -> bool:
    """Require at least one domain keyword in the title (from profile.yml title_domain)."""
    if not _TITLE_DOMAIN_RES:
        return True  # no domain filter configured
    title = offer.title or ""
    return any(r.search(title) for r in _TITLE_DOMAIN_RES)


def _title_exclude_allowed(offer: JobOffer) -> bool:
    """Reject offers whose title matches an excluded pattern (from profile.yml title_exclude)."""
    if not _TITLE_EXCLUDE_RE:
        return True
    title = offer.title or ""
    return not _TITLE_EXCLUDE_RE.search(title)


def apply_filters(offers: list[JobOffer]) -> tuple[list[JobOffer], dict[str, int]]:
    result = []
    reasons: dict[str, int] = {
        "contract": 0, "salary": 0, "experience": 0,
        "title_exclude": 0, "title_domain": 0, "age": 0,
    }
    for offer in offers:
        if not _contract_allowed(offer):
            reasons["contract"] += 1
        elif not _salary_allowed(offer):
            reasons["salary"] += 1
        elif not _experience_allowed(offer):
            reasons["experience"] += 1
        elif not _title_exclude_allowed(offer):
            reasons["title_exclude"] += 1
        elif not _title_domain_allowed(offer):
            reasons["title_domain"] += 1
        elif not _age_allowed(offer):
            reasons["age"] += 1
        else:
            result.append(offer)
    return result, reasons
