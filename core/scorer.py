import re

import config
from models import JobOffer

_GRADE_THRESHOLDS = [
    (4.0, "A"),
    (3.0, "B"),
    (2.0, "C"),
    (1.0, "D"),
    (0.0, "F"),
]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def _score_keywords(offer: JobOffer) -> float:
    """0–2: count preferred_keyword hits in title + description."""
    keywords = [kw.lower() for kw in config.SCORING_PREFERRED_KEYWORDS]
    text = " ".join(filter(None, [offer.title, offer.description])).lower()
    hits = sum(1 for kw in keywords if kw in text)
    if hits == 0:
        return 0.0
    if hits <= 2:
        return 1.0
    return 2.0


def _score_salary(offer: JobOffer) -> float:
    """0–1: salary attractiveness relative to minimum and target."""
    if offer.salary_min is None:
        return 0.0
    if offer.salary_min >= config.SCORING_TARGET_SALARY:
        return 1.0
    if offer.salary_min >= config.SALARY_MIN:
        return 0.5
    return 0.0


def _score_remote(offer: JobOffer) -> float:
    """0–1: match against preferred remote type."""
    preferred = config.SCORING_PREFERRED_REMOTE
    if preferred is None:
        return 0.5
    if offer.remote_type == preferred:
        return 1.0
    if offer.remote_type is None:
        return 0.5  # unknown — don't penalise
    return 0.0


def _score_experience(offer: JobOffer) -> float:
    """0–1: favour junior/entry-level requirements."""
    exp = offer.experience
    if exp is None:
        return 1.0
    exp_lower = exp.lower()
    if "débutant" in exp_lower or "debutant" in exp_lower:
        return 1.0
    match = re.search(r"\d+", exp_lower)
    if match:
        years = int(match.group())
        if years <= 2:
            return 0.75
        if years <= 4:
            return 0.5
        return 0.0
    return 0.75  # vague experience mention — mild penalty


def score_offer(offer: JobOffer) -> None:
    """Compute and set score + grade on the offer in-place."""
    total = (
        _score_keywords(offer)
        + _score_salary(offer)
        + _score_remote(offer)
        + _score_experience(offer)
    )
    offer.score = round(total, 2)
    offer.grade = _grade(total)


def score_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """Score all offers in-place and return them sorted by score descending."""
    for offer in offers:
        score_offer(offer)
    offers.sort(key=lambda o: o.score or 0.0, reverse=True)
    return offers
