"""
Enrich job offers by extracting structured fields from their description
using a local Ollama model (qwen2.5 by default).

Only fills fields that are explicitly stated in the description — never invents.
"""

import json
import re

import requests
from tqdm import tqdm

from models import JobOffer

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:4b"

# Fields that may be missing and can be found in the description
_ENRICHABLE_FIELDS = ("company", "contract_type", "salary_min", "salary_max", "remote_type", "experience")

# Fields that are always checked against the description, even if the API already provided a value,
# because the API value can be inaccurate (e.g. "Débutant accepté" when the description says 10 years).
_ALWAYS_CHECK_FIELDS = ("experience",)

_FIELD_DESCRIPTIONS = {
    "company": (
        "Name of the hiring company or organisation as explicitly stated in the job description. "
        "Return the exact name or null if not mentioned."
    ),
    "contract_type": (
        'Type of employment contract (e.g. "CDI", "CDD", "Freelance", "Alternance", "Stage"). '
        "Return a short string or null."
    ),
    "salary_min": (
        "Minimum annual gross salary in euros, as a plain number (no symbol, no separator). "
        "Rules: "
        "(1) Only extract a fixed base salary explicitly stated in the description — never infer or estimate from job level. "
        "(2) Ignore bonus percentages, variable pay percentages, or performance targets (e.g. '300% des objectifs' is not a salary). "
        "(3) If salary is a range (e.g. '45 000 € à 55 000 €' or '40k€–50k€'), return the lower bound as salary_min. "
        "(4) Convert 'k€' or 'K€' to full number (e.g. '40k€' → 40000). "
        "(5) Convert monthly salary to annual by multiplying by 12. "
        "(6) Convert daily rate (e.g. '300 €/jour') to annual by multiplying by 220. "
        "If no explicit base salary figure is stated, return null."
    ),
    "salary_max": (
        "Maximum annual gross salary in euros, as a plain number. "
        "Only set when the description states a salary range — return the upper bound. "
        "Apply the same conversion rules as salary_min (k€, monthly, daily rate). "
        "If only a single salary figure is stated (not a range), return null. "
        "If no explicit base salary is stated, return null."
    ),
    "remote_type": (
        'Work arrangement. Must be exactly one of: "remote", "hybrid", "on-site", or null. '
        '"remote" = fully remote / 100% télétravail. '
        '"hybrid" = partial remote / télétravail partiel / quelques jours par semaine. '
        '"on-site" = no remote / présentiel / sur site. '
        "If no work arrangement is mentioned, return null."
    ),
    "experience": (
        "Years of experience explicitly required. "
        "Return the shortest phrase that captures it (e.g. '2 ans', '5 à 8 ans', '10 ans minimum'). "
        "If the description only says 'Débutant accepté' or equivalent, return 'Débutant accepté'. "
        "If only vague qualifiers are used (e.g. 'forte expérience', 'expérience significative') without a number, return null. "
        "If nothing is stated about experience, return null."
    ),
}


def _fields_to_check(offer: JobOffer) -> list[str]:
    """Return fields to send to the LLM: missing fields + always-check fields (if description exists)."""
    missing = {f for f in _ENRICHABLE_FIELDS if getattr(offer, f) is None}
    always = set(_ALWAYS_CHECK_FIELDS)
    return [f for f in _ENRICHABLE_FIELDS if f in missing or f in always]


def _needs_enrichment(offer: JobOffer) -> bool:
    return bool(offer.description) and bool(_fields_to_check(offer))


def _build_prompt(offer: JobOffer, missing: list[str]) -> str:
    fields_spec = "\n".join(
        f'  "{f}": {_FIELD_DESCRIPTIONS[f]}' for f in missing
    )
    return (
        "You are a precise information extractor. "
        "Read the job description below and extract ONLY the information that is EXPLICITLY stated. "
        "Do NOT infer, guess, or invent anything. "
        "If a piece of information is not clearly stated, return null for that field.\n\n"
        f"Job title: {offer.title}\n\n"
        f"Job description:\n{offer.description}\n\n"
        "Return a JSON object with ONLY the following fields:\n"
        f"{fields_spec}\n\n"
        "Respond with valid JSON only, no explanation."
    )


def _call_ollama(prompt: str) -> dict | None:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "think": False,
                "options": {"temperature": 0},
            },
            timeout=300,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return json.loads(content)
    except requests.exceptions.ConnectionError:
        tqdm.write(f"  ! Ollama not reachable at {OLLAMA_URL} — skipping enrichment.")
        return None
    except Exception as exc:
        tqdm.write(f"  ! Ollama call failed: {exc}")
        return None


def _apply_extracted(offer: JobOffer, extracted: dict, fields: list[str]) -> None:
    """Mutate offer in-place, setting fields from description when available."""
    always_check = set(_ALWAYS_CHECK_FIELDS)
    for field in fields:
        if field not in extracted:
            continue  # LLM didn't address this field — leave as-is
        value = extracted[field]
        if value is None:
            # For always-check fields, explicit null means the description doesn't
            # state it — clear the potentially wrong API value.
            if field in always_check and getattr(offer, field) is not None:
                setattr(offer, field, None)
                tqdm.write(f"    ~ cleared  {field}")
            continue

        if field in ("salary_min", "salary_max"):
            if isinstance(value, (int, float)):
                setattr(offer, field, float(value))
                tqdm.write(f"    + {field} = {float(value)}")
            elif isinstance(value, str):
                cleaned = re.sub(r"[^\d.]", "", value.replace(",", "."))
                if cleaned:
                    setattr(offer, field, float(cleaned))
                    tqdm.write(f"    + {field} = {float(cleaned)}")
        elif field == "remote_type":
            if value in ("remote", "hybrid", "on-site"):
                offer.remote_type = value
                tqdm.write(f"    + remote_type = {value}")
        else:
            if isinstance(value, str) and value.strip():
                setattr(offer, field, value.strip())
                tqdm.write(f"    + {field} = {value.strip()!r}")


def enrich_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """
    For each offer with a description and missing fields, call Ollama to fill the blanks.
    Returns the same list (mutated in-place) for convenience.
    """
    to_enrich = [(i, offer) for i, offer in enumerate(offers) if _needs_enrichment(offer)]

    if not to_enrich:
        return offers

    with tqdm(total=len(to_enrich), unit="offer", desc="  Enriching") as bar:
        for _, offer in to_enrich:
            fields = _fields_to_check(offer)
            bar.set_postfix_str(offer.title[:40])

            prompt = _build_prompt(offer, fields)
            extracted = _call_ollama(prompt)

            if extracted is None:
                # Ollama is unreachable — abort the whole enrichment pass
                bar.close()
                break

            _apply_extracted(offer, extracted, fields)
            bar.update(1)

    return offers
