import re

import requests

import config
from models import JobOffer
from sources.base import JobSource

_TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)
_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
_SCOPE = "api_offresdemploiv2 o2dsoffre"


def _get_access_token() -> str:
    if not config.FRANCE_TRAVAIL_CLIENT_ID or not config.FRANCE_TRAVAIL_CLIENT_SECRET:
        raise EnvironmentError(
            "Missing FRANCE_TRAVAIL_CLIENT_ID or FRANCE_TRAVAIL_CLIENT_SECRET in .env"
        )
    response = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": config.FRANCE_TRAVAIL_CLIENT_ID,
            "client_secret": config.FRANCE_TRAVAIL_CLIENT_SECRET,
            "scope": _SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


_PAGE_SIZE = 150  # API hard cap per request


def _parse_total(content_range: str) -> int | None:
    """Extract total from Content-Range header, e.g. 'offres 0-149/832' → 832."""
    try:
        return int(content_range.split("/")[1])
    except (IndexError, ValueError):
        return None


class FranceTravailSource(JobSource):

    @property
    def name(self) -> str:
        return "france_travail"

    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        token = _get_access_token()

        params: dict[str, str] = {"motsCles": keywords}
        if location:
            params["departement"] = location

        collected: list[JobOffer] = []
        offset = 0

        while len(collected) < max_results:
            end = min(offset + _PAGE_SIZE, max_results) - 1
            response = requests.get(
                _SEARCH_URL,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Range": f"offres {offset}-{end}",
                },
                timeout=15,
            )
            if not response.ok:
                raise RuntimeError(f"{response.status_code} {response.reason}: {response.text}")

            if response.status_code == 204 or not response.content:
                break

            page = response.json().get("resultats", [])
            collected.extend(_map_offer(item, self.name) for item in page)

            total = _parse_total(response.headers.get("Content-Range", ""))
            if total is None or offset + _PAGE_SIZE >= total:
                break

            offset += _PAGE_SIZE

        return collected


def _parse_remote_type(item: dict) -> str | None:
    raw = (item.get("modesTravailLibelle") or "").lower()
    if not raw:
        return None
    if "complet" in raw or "total" in raw:
        return "remote"
    if "partiel" in raw or "hybride" in raw or "mixte" in raw:
        return "hybrid"
    if "présentiel" in raw or "presentiel" in raw or "bureau" in raw:
        return "on-site"
    return None


def _parse_salary(libelle: str) -> tuple[float | None, float | None]:
    """Parse salary min/max (annual €) from a FranceTravail libelle string."""
    if not libelle:
        return None, None
    lower = libelle.lower()
    if "horaire" in lower:
        return None, None  # Hourly rates are too hard to annualise reliably

    # Extract all amounts preceding "euros" — this avoids matching the month count
    amounts = re.findall(r"([\d]+(?:[.,]\d+)?)\s*euros?", lower)
    if not amounts:
        return None, None

    values = [float(a.replace(",", ".")) for a in amounts]
    salary_min = values[0]
    salary_max = values[1] if len(values) > 1 else None

    if "mensuel" in lower:
        months_match = re.search(r"sur\s+([\d]+(?:[.,]\d+)?)\s*mois", lower)
        months = float(months_match.group(1).replace(",", ".")) if months_match else 12.0
        salary_min *= months
        if salary_max is not None:
            salary_max *= months

    # Reject implausible annual figures — likely a unit error in the API data
    if salary_min > 300_000:
        return None, None

    return salary_min, salary_max


def _map_offer(item: dict, source_name: str) -> JobOffer:
    libelle = (item.get("salaire") or {}).get("libelle") or ""
    salary_min, salary_max = _parse_salary(libelle)

    return JobOffer(
        title=item.get("intitule", ""),
        company=item.get("entreprise", {}).get("nom") or None,
        location=item.get("lieuTravail", {}).get("libelle", ""),
        url=item.get("origineOffre", {}).get("urlOrigine", ""),
        source=source_name,
        posted_at=item.get("dateCreation"),
        description=item.get("description"),
        contract_type=item.get("typeContratLibelle"),
        salary_min=salary_min,
        salary_max=salary_max,
        remote_type=_parse_remote_type(item),
        experience=item.get("experienceLibelle"),
    )
