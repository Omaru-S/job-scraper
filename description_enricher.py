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
OLLAMA_MODEL = "qwen3.5:latest"

# Fields that may be missing and can be found in the description
_ENRICHABLE_FIELDS = ("contract_type", "salary_min", "salary_max", "remote_type", "experience")

# Fields that are always checked against the description, even if the API already provided a value,
# because the API value can be inaccurate (e.g. "Débutant accepté" when the description says 10 years).
_ALWAYS_CHECK_FIELDS = ("experience",)

_FIELD_DESCRIPTIONS = {
    "contract_type": (
        'Type of employment contract (e.g. "CDI", "CDD", "Freelance", "Alternance", "Stage"). '
        "Return a short string or null."
    ),
    "salary_min": (
        "Minimum annual salary in euros as a number (no currency symbol, no thousands separator). "
        "Convert monthly salaries to annual. Return a number or null."
    ),
    "salary_max": (
        "Maximum annual salary in euros as a number. "
        "Return a number or null."
    ),
    "remote_type": (
        'Work arrangement. Must be exactly one of: "remote", "hybrid", "on-site", or null. '
        '"remote" = fully remote, "hybrid" = partial remote, "on-site" = no remote.'
    ),
    "experience": (
        "Years or level of experience explicitly required in the description "
        '(e.g. "3 ans", "10 ans", "Débutant accepté"). '
        "If the description states a specific number of years, return that — "
        "it takes precedence over any general label. Return null only if the description says nothing about experience."
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
        print(f"[enricher] Ollama not reachable at {OLLAMA_URL}. Skipping enrichment.")
        return None
    except Exception as exc:
        print(f"[enricher] Ollama call failed: {exc}")
        return None


def _apply_extracted(offer: JobOffer, extracted: dict, fields: list[str]) -> None:
    """Mutate offer in-place, setting fields from description when available."""
    for field in fields:
        value = extracted.get(field)
        if value is None:
            continue

        if field in ("salary_min", "salary_max"):
            # Accept numeric strings like "45000" or "45 000"
            if isinstance(value, (int, float)):
                setattr(offer, field, float(value))
                print(f"    [enriched] {field} = {float(value)}")
            elif isinstance(value, str):
                cleaned = re.sub(r"[^\d.]", "", value.replace(",", "."))
                if cleaned:
                    setattr(offer, field, float(cleaned))
                    print(f"    [enriched] {field} = {float(cleaned)}")
        elif field == "remote_type":
            if value in ("remote", "hybrid", "on-site"):
                offer.remote_type = value
                print(f"    [enriched] remote_type = {value}")
        else:
            # contract_type, experience — plain strings
            if isinstance(value, str) and value.strip():
                setattr(offer, field, value.strip())
                print(f"    [enriched] {field} = {value.strip()!r}")


def enrich_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """
    For each offer with a description and missing fields, call Ollama to fill the blanks.
    Returns the same list (mutated in-place) for convenience.
    """
    to_enrich = [(i, offer) for i, offer in enumerate(offers) if _needs_enrichment(offer)]

    if not to_enrich:
        return offers

    print(f"[enricher] {len(to_enrich)}/{len(offers)} offers to enrich via Ollama ({OLLAMA_MODEL})")

    with tqdm(total=len(to_enrich), unit="offer", desc="Enriching") as bar:
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
