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


def _build_range(max_results: int) -> str:
    # Pagination uses an HTTP Range header: "offres 0-49"
    # API enforces a hard cap of 150 results per call
    end = min(max_results, 150) - 1
    return f"offres 0-{end}"


class FranceTravailSource(JobSource):

    @property
    def name(self) -> str:
        return "france_travail"

    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        token = _get_access_token()

        params: dict[str, str] = {"motsCles": keywords}
        if location:
            params["departement"] = location

        response = requests.get(
            _SEARCH_URL,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Range": _build_range(max_results),
            },
            timeout=15,
        )
        if not response.ok:
            raise RuntimeError(f"{response.status_code} {response.reason}: {response.text}")

        # 204 No Content = zero results for this keyword
        if response.status_code == 204 or not response.content:
            return []

        raw_offers = response.json().get("resultats", [])

        return [_map_offer(item, self.name) for item in raw_offers]


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

    return salary_min, salary_max


def _map_offer(item: dict, source_name: str) -> JobOffer:
    libelle = (item.get("salaire") or {}).get("libelle") or ""
    salary_min, salary_max = _parse_salary(libelle)

    return JobOffer(
        title=item.get("intitule", ""),
        company=item.get("entreprise", {}).get("nom", "N/A"),
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
