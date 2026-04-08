import re

import config
from models import JobOffer

# Contract type codes as returned by the FranceTravail API
_EXCLUDED_CONTRACTS = {"mission intérimaire", "contrat apprentissage", "alternance"}
_VIE_KEYWORDS = {"vie", "via", "volontariat international"}


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

    # Exclude everything else (CDD, interim, alternance, stage, etc.)
    return False


def _experience_allowed(offer: JobOffer) -> bool:
    if not offer.experience:
        return True
    exp = offer.experience.lower()
    if "débutant" in exp or "debutant" in exp:
        return True
    if "exig" in exp:
        return False
    # "> 6 mois" — months are always junior enough
    if "mois" in exp:
        return True
    # "> 1 an", "2 ans d'expérience", etc. — extract the year count
    match = re.search(r"\d+", exp)
    if match:
        return int(match.group()) <= 2
    return True


def _salary_allowed(offer: JobOffer) -> bool:
    if offer.salary_min is None:
        return not config.REQUIRE_SALARY
    return offer.salary_min >= config.SALARY_MIN


def apply_filters(offers: list[JobOffer]) -> tuple[list[JobOffer], dict[str, int]]:
    result = []
    reasons: dict[str, int] = {"contract": 0, "salary": 0, "experience": 0}
    for offer in offers:
        if not _contract_allowed(offer):
            reasons["contract"] += 1
        elif not _salary_allowed(offer):
            reasons["salary"] += 1
        elif not _experience_allowed(offer):
            reasons["experience"] += 1
        else:
            result.append(offer)
    return result, reasons
