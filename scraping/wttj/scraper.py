"""
Welcome to the Jungle scraper.

Two responsibilities:
  - search_jobs(keyword, location, max_pages) → list of CardResult
  - scrape_job(url) → dict of job fields (matching JobOffer)
"""

import re
import logging
from dataclasses import dataclass
from urllib.parse import quote_plus

import config
from scrapling.fetchers import DynamicFetcher
from scrapling.core.utils import set_logger as _scrapling_set_logger

logger = logging.getLogger(__name__)

# Scrapling uses a ContextVar logger — silence it in every thread that calls us.
_scrapling_silent = logging.getLogger("scrapling")
_scrapling_silent.setLevel(logging.WARNING)


def _silence_scrapling() -> None:
    """Call once per thread to suppress scrapling's INFO fetch logs."""
    _scrapling_set_logger(_scrapling_silent)

BASE_URL = "https://www.welcometothejungle.com"
SEARCH_URL = BASE_URL + "/fr/jobs?query={query}&aroundQuery={location}&page={page}"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CardResult:
    url: str
    title: str
    company: str | None
    contract_type: str | None


# ---------------------------------------------------------------------------
# Pre-filtering
# ---------------------------------------------------------------------------

_CONTRACT_EXCLUDE = {"Alternance", "Stage", "VIE"}

# Hard-coded sourcing exclusions (contract/role type — always excluded regardless of profile)
_TITLE_EXCLUDE_HARD = re.compile(
    r"\b("
    r"alternance|alternant[e]?"
    r"|stage|stagiaire"
    r"|vie\b"
    r"|commerci[ae]l[e]?"
    r"|avant[- ]vente"
    r"|ingénieur[e]?\s+d['\u2019]affaires"
    r"|account\s+manager"
    r"|\bmanager\b"
    r")",
    re.IGNORECASE,
)

# Profile-driven exclusions loaded from profile.yml
_TITLE_EXCLUDE_PROFILE = (
    re.compile(
        r"\b(" + "|".join(re.escape(p) for p in config.TITLE_EXCLUDE_PATTERNS) + r")\b",
        re.IGNORECASE,
    )
    if config.TITLE_EXCLUDE_PATTERNS else None
)

# Profile-driven domain requirement loaded from profile.yml
_TITLE_DOMAIN_RES = [
    re.compile(re.escape(kw), re.IGNORECASE)
    for kw in config.TITLE_DOMAIN_KEYWORDS
]

_CONTRACT_PATTERN = re.compile(
    r"^(CDI|CDD|Freelance|Stage|Alternance|Intérim|VIE)$"
)


def _is_relevant(title: str | None, contract_type: str | None) -> bool:
    if contract_type in _CONTRACT_EXCLUDE:
        return False
    if not title:
        return True
    if _TITLE_EXCLUDE_HARD.search(title):
        return False
    if _TITLE_EXCLUDE_PROFILE and _TITLE_EXCLUDE_PROFILE.search(title):
        return False
    if _TITLE_DOMAIN_RES and not any(r.search(title) for r in _TITLE_DOMAIN_RES):
        return False
    return True


# ---------------------------------------------------------------------------
# Search page
# ---------------------------------------------------------------------------

def search_jobs(keyword: str, location: str = "Paris", max_pages: int = 3) -> list[CardResult]:
    """
    Scrape WTTJ search results, pre-filter irrelevant cards, and return
    a deduplicated list of CardResult. Each page yields ~30 cards.
    """
    _silence_scrapling()
    seen: set[str] = set()
    results: list[CardResult] = []

    for page_num in range(1, max_pages + 1):
        url = SEARCH_URL.format(
            query=quote_plus(keyword),
            location=quote_plus(location),
            page=page_num,
        )
        logger.debug("Searching page %d: %s", page_num, url)
        page = DynamicFetcher.fetch(url, network_idle=True, headless=True)

        cards = page.css('[data-testid^="job-thumb-"]')
        new_on_page = 0
        filtered_on_page = 0

        for card in cards:
            link = card.css("a")[0] if card.css("a") else None
            if not link:
                continue

            href = link.attrib.get("href", "")
            if not href or href in seen:
                continue

            aria = link.attrib.get("aria-label", "")
            title = aria.removeprefix("Consultez l'offre ").strip() or None

            # Contract type from card text tokens
            tokens = [t.strip() for t in card.css("*::text").getall() if t.strip()]
            contract_type = next(
                (t for t in tokens if _CONTRACT_PATTERN.match(t)), None
            )

            # Company name from logo img alt
            logo = card.css("img[data-testid^='job-thumb-logo-']")
            company = logo[0].attrib.get("alt") if logo else None

            seen.add(href)

            if not _is_relevant(title, contract_type):
                filtered_on_page += 1
                logger.debug("  Filtered: %r (%s)", title, contract_type)
                continue

            results.append(CardResult(
                url=BASE_URL + href,
                title=title,
                company=company,
                contract_type=contract_type,
            ))
            new_on_page += 1

        logger.debug(
            "Page %d: %d kept, %d filtered (total: %d)",
            page_num, new_on_page, filtered_on_page, len(results),
        )

        if new_on_page + filtered_on_page == 0:
            break

    return results


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def _tokens(el) -> list[str]:
    return [t.strip() for t in el.css("*::text").getall() if t.strip()]


_EXP_FROM_TEXT = re.compile(
    r"(\d+)\s*\+?\s*(?:years?|ans?)\b",
    re.IGNORECASE,
)

_EXP_CONTEXT = re.compile(
    r"(?:experience?|expérience|proficiency|professional|minimum|required|requis)",
    re.IGNORECASE,
)


def _extract_experience_from_text(text: str | None) -> str | None:
    """
    Fallback: scan free-text for the highest year requirement near an
    experience-related keyword (e.g. "5+ years of experience").
    Returns a normalised string like "5+ ans" or None.
    """
    if not text:
        return None
    best: int | None = None
    for m in _EXP_FROM_TEXT.finditer(text):
        # Only count if an experience-related word appears within ±120 chars
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 120)
        window = text[start:end]
        if not _EXP_CONTEXT.search(window):
            continue
        years = int(m.group(1))
        if best is None or years > best:
            best = years
    if best is None:
        return None
    return f"{best}+ ans"


def _normalize_remote(raw: str | None) -> str | None:
    if not raw:
        return None
    r = raw.lower()
    if "total" in r or "full" in r or "100" in r:
        return "remote"
    if "fréquent" in r or "partiel" in r or "occasionnel" in r or "hybride" in r:
        return "hybrid"
    if "non autorisé" in r or "présentiel" in r or "sur site" in r:
        return "on-site"
    return None


def _parse_salary(raw: str) -> tuple[float | None, float | None]:
    is_upper = bool(re.search(r"^[<«]", raw.strip()))
    normalized = raw.replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    numbers = re.findall(r"\d+(?:[.,]\d+)?[Kk]?", normalized)
    values: list[float] = []
    for n in numbers:
        n = n.replace(",", ".")
        if n.lower().endswith("k"):
            values.append(float(n[:-1]) * 1000)
        else:
            try:
                values.append(float(n))
            except ValueError:
                pass
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return (None, values[0]) if is_upper else (values[0], None)
    return None, None


def _parse_metadata(tokens: list[str]) -> dict:
    result: dict = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.match(r"Salaire", tok) and i + 1 < len(tokens):
            result["salary_raw"] = tokens[i + 1]
            i += 2
        elif re.match(r"Expérience", tok) and i + 1 < len(tokens):
            result["experience"] = tokens[i + 1]
            i += 2
        elif re.match(r"Éducation", tok) and i + 1 < len(tokens):
            result["education"] = tokens[i + 1]
            i += 2
        elif re.match(r"(CDI|CDD|Freelance|Stage|Alternance|Intérim|VIE)", tok):
            result["contract_type"] = tok
            i += 1
        elif re.match(r"Télétravail|Full.?remote|Présentiel", tok, re.I):
            result["remote_type"] = _normalize_remote(tok)
            i += 1
        elif re.match(r"il y a|aujourd", tok):
            result["posted_at"] = tok
            i += 1
        else:
            i += 1
    return result


def _expand_voir_plus(pw_page) -> None:
    """
    Click the 'Voir plus' link inside the job description so that truncated
    content is fully expanded before we scrape the DOM.
    WTTJ renders this as <a data-testid="view-more-btn"> (not a <button>).
    """
    try:
        # Target only the view-more link inside the description section
        btn = pw_page.locator(
            '[data-testid="job-section-description"] [data-testid="view-more-btn"]'
        ).first
        if btn.count() and btn.is_visible():
            btn.click()
            pw_page.wait_for_load_state("networkidle")
    except Exception:
        pass


def scrape_job(url: str) -> dict:
    """
    Fetch a single WTTJ job page and return a dict of structured fields.
    Safe to call from multiple threads — silences scrapling logs per-thread.
    Raises ValueError on 404.
    """
    _silence_scrapling()
    page = DynamicFetcher.fetch(url, network_idle=True, headless=True, page_action=_expand_voir_plus)

    if page.css('[data-testid="error-page-404"]'):
        raise ValueError(f"404 — job listing not found: {url}")

    meta = page.css('[data-testid="job-metadata-block"]')

    title = meta.css("h2::text").get() if meta else page.css("h2::text").get()
    company = meta.css('a[href*="/fr/companies/"] span::text').get() if meta else None

    all_tokens = _tokens(meta) if meta else []
    parsed = _parse_metadata(all_tokens)

    location = None
    contract = parsed.get("contract_type", "")
    if contract and contract in all_tokens:
        idx = all_tokens.index(contract)
        if idx + 1 < len(all_tokens):
            location = all_tokens[idx + 1].strip(", ")

    salary_min, salary_max = _parse_salary(parsed.get("salary_raw", ""))

    desc_nodes = page.css('[data-testid="job-section-description"] *::text').getall()
    description = " ".join(t.strip() for t in desc_nodes if t.strip()) or None

    profile_nodes = page.css('[data-testid="job-section-experience"] *::text').getall()
    profile = " ".join(t.strip() for t in profile_nodes if t.strip()) or None

    experience = parsed.get("experience") or _extract_experience_from_text(
        (profile or "") + " " + (description or "")
    )

    return {
        "url": url,
        "source": "welcome_to_the_jungle",
        "title": title,
        "company": company,
        "location": location,
        "contract_type": parsed.get("contract_type"),
        "remote_type": parsed.get("remote_type"),
        "salary_raw": parsed.get("salary_raw"),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "experience": experience,
        "education": parsed.get("education"),
        "posted_at": parsed.get("posted_at"),
        "description": description,
        "profile": profile,
    }
