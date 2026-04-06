from dataclasses import fields as dataclass_fields

from models import JobOffer

_REQUIRED_FIELDS = ("title", "url", "source", "location")
_VALID_REMOTE_TYPES = {"remote", "hybrid", "on-site"}


def _validate_offer(offer: JobOffer) -> list[str]:
    issues = []

    for field in _REQUIRED_FIELDS:
        value = getattr(offer, field)
        if not value or (isinstance(value, str) and not value.strip()):
            issues.append(f"missing required field '{field}'")

    if offer.url and not offer.url.startswith("http"):
        issues.append(f"malformed URL: {offer.url!r}")

    if offer.remote_type is not None and offer.remote_type not in _VALID_REMOTE_TYPES:
        issues.append(f"invalid remote_type: {offer.remote_type!r}")

    if offer.salary_min is not None and offer.salary_min <= 0:
        issues.append(f"non-positive salary_min: {offer.salary_min}")

    if offer.salary_max is not None and offer.salary_max <= 0:
        issues.append(f"non-positive salary_max: {offer.salary_max}")

    if offer.salary_min is not None and offer.salary_max is not None:
        if offer.salary_min > offer.salary_max:
            issues.append(
                f"salary_min ({offer.salary_min}) > salary_max ({offer.salary_max})"
            )

    return issues


def validate_offers(offers: list[JobOffer]) -> bool:
    """
    Validate all offers and print a summary of any issues found.
    Returns True if all offers are valid, False if any issues were found.
    """
    invalid: list[tuple[JobOffer, list[str]]] = []

    for offer in offers:
        issues = _validate_offer(offer)
        if issues:
            invalid.append((offer, issues))

    if not invalid:
        print(f"Validation: all {len(offers)} offers are valid.")
        return True

    print(f"Validation: {len(invalid)}/{len(offers)} offers have issues:")
    for offer, issues in invalid:
        label = f"'{offer.title}' @ {offer.company or '?'}"
        for issue in issues:
            print(f"  [invalid] {label} — {issue}")

    return False
