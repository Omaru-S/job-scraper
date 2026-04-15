"""
Mon Vie Via (mon-vie-via.businessfrance.fr) scraper.

Two responsibilities:
  - list_offers(max_scrolls) → list of CardResult  (filtered to target countries)
  - scrape_offer(url)        → dict of job fields   (matching JobOffer)

The site is a Nuxt/Vue SPA — all pages require Playwright rendering.
"""

import re
import logging
from dataclasses import dataclass

from scrapling.fetchers import DynamicFetcher
from scrapling.core.utils import set_logger as _scrapling_set_logger

logger = logging.getLogger(__name__)

_scrapling_silent = logging.getLogger("scrapling")
_scrapling_silent.setLevel(logging.WARNING)

BASE_URL = "https://mon-vie-via.businessfrance.fr"
SEARCH_URL = BASE_URL + "/offres/recherche"

# Target countries in French uppercase, as displayed in `.location` cards
# Used both for the website filter UI and as a safety-net check on card text
_TARGET_COUNTRIES = frozenset({"JAPON", "ETATS-UNIS", "SINGAPOUR", "SUISSE"})

# The Zone/Pays multiselects are at fixed indices in .multiselect.standard
# (Spécialisation=0, Type=1, Durée=2, Zone=3, Pays=4, ...)
_ZONE_INDEX = 3
_PAYS_INDEX = 4

_TARGET_ZONES = ["AMERIQUE DU NORD", "ASIE ET PACIFIQUE", "EUROPE OCCIDENTALE"]
_TARGET_PAYS  = ["ETATS-UNIS", "JAPON", "SINGAPOUR", "SUISSE"]

_MONTHS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CardResult:
    url: str
    title: str | None
    company: str | None
    location: str | None   # e.g. "JAPON - TOKYO"
    contract_type: str | None  # "VIE" or "VIA"
    duration: str | None   # e.g. "18 mois"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _silence_scrapling() -> None:
    _scrapling_set_logger(_scrapling_silent)


def _is_target_country(location: str | None) -> bool:
    if not location:
        return False
    loc = location.upper()
    return any(c in loc for c in _TARGET_COUNTRIES)


def _parse_french_date(text: str) -> str | None:
    """Convert 'DD mois YYYY' → 'YYYY-MM-DD' for ISO parsing in the pipeline."""
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if not m:
        return None
    day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTHS_FR.get(month_name)
    if not month:
        return None
    return f"{year}-{month:02d}-{int(day):02d}"


def _joined(el, selector: str) -> str | None:
    texts = [t.strip() for t in el.css(selector).getall() if t.strip()]
    return " ".join(texts) or None


# ---------------------------------------------------------------------------
# Listing page — click "Voir plus d'offres" until exhausted, filter by country
# ---------------------------------------------------------------------------

def _filter_and_load_action(max_clicks: int):
    """
    page_action:
    1. Dismiss the Didomi cookie consent popup.
    2. Use the site's Zone filter to select the 3 target regions, then use
       the Pays filter to narrow to the 4 target countries. Both dropdowns
       close after each click so we re-open them per value.
    3. Click 'Voir plus d'offres' until all filtered results are loaded.
    """
    def _action(pw_page) -> None:
        # ── Step 1: dismiss cookie banner ──────────────────────────────────
        try:
            reject_btn = pw_page.locator("button.didomi-disagree-button").first
            if reject_btn.count() and reject_btn.is_visible():
                reject_btn.click()
                pw_page.wait_for_selector("#didomi-host", state="hidden", timeout=6000)
                pw_page.wait_for_timeout(800)
        except Exception:
            pass

        # ── Step 2: select target zones ────────────────────────────────────
        zone_ms = pw_page.locator(".multiselect.standard").nth(_ZONE_INDEX)
        for zone in _TARGET_ZONES:
            try:
                zone_ms.click()
                pw_page.wait_for_timeout(500)
                opt = pw_page.locator(".multiselect__option").filter(has_text=zone).first
                if opt.is_visible(timeout=2000):
                    opt.click()
                    pw_page.wait_for_timeout(600)
            except Exception:
                pass

        # ── Step 3: select target countries ────────────────────────────────
        pays_ms = pw_page.locator(".multiselect.standard").nth(_PAYS_INDEX)
        for pays in _TARGET_PAYS:
            try:
                pays_ms.click()
                pw_page.wait_for_timeout(500)
                opt = pw_page.locator(".multiselect__option").filter(has_text=pays).first
                if opt.is_visible(timeout=2000):
                    opt.click()
                    pw_page.wait_for_timeout(600)
            except Exception:
                pass

        # ── Step 4: click "Voir plus d'offres" until the button disappears ──
        # max_clicks is a safety ceiling only — we always try to exhaust all.
        for _ in range(max_clicks):
            try:
                btn = pw_page.locator("a.see-more-btn, button.see-more-btn").first
                if not (btn.count() and btn.is_visible()):
                    break  # no more offers to load
                before = pw_page.locator(".figure_container").count()
                btn.scroll_into_view_if_needed()
                btn.click()
                try:
                    pw_page.wait_for_function(
                        f"document.querySelectorAll('.figure_container').length > {before}",
                        timeout=12000,
                    )
                except Exception:
                    # Timeout: check manually — if count grew, keep going;
                    # if not, the button is likely stuck or gone.
                    pw_page.wait_for_timeout(2000)
                after = pw_page.locator(".figure_container").count()
                if after == before:
                    break  # click had no effect — truly at the end
            except Exception:
                break
    return _action


def list_offers(max_clicks: int = 500) -> list[CardResult]:
    """
    Fetch the MVV listing page, click 'Voir plus d'offres' until the button
    disappears (all offers loaded), and return those in the target countries.
    max_clicks is a safety ceiling — in practice the loop stops when the
    button is gone.
    """
    _silence_scrapling()

    page = DynamicFetcher.fetch(
        SEARCH_URL,
        network_idle=True,
        headless=True,
        page_action=_filter_and_load_action(max_clicks),
    )

    results: list[CardResult] = []
    seen: set[str] = set()

    for card in page.css(".figure_container"):
        company = (card.css("h3.organization-name::text").get() or "").strip() or None
        title   = (card.css("h2.mission-title::text").get() or "").strip() or None
        location = (card.css("h2.location::text").get() or "").strip() or None

        li_items = [li.css("::text").get() or "" for li in card.css("ul.meta-list li")]
        contract_type = li_items[0].strip() if li_items else None
        duration      = li_items[1].strip() if len(li_items) > 1 else None

        href = card.css("a.postuler::attr(href)").get()
        if not href or href in seen:
            continue
        seen.add(href)

        if not _is_target_country(location):
            logger.debug("  Skipping non-target country: %r", location)
            continue

        url = BASE_URL + href if href.startswith("/") else href
        results.append(CardResult(
            url=url,
            title=title,
            company=company,
            location=location,
            contract_type=contract_type,
            duration=duration,
        ))
        logger.debug("  Kept: %r @ %r", title, location)

    logger.debug("list_offers: %d matching offers found", len(results))
    return results


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def scrape_offer(url: str) -> dict:
    """
    Fetch a single MVV offer page and return a dict of structured fields.
    Safe to call from multiple threads.
    """
    _silence_scrapling()
    page = DynamicFetcher.fetch(url, network_idle=True, headless=True)

    # ── Header block (company / title / city / contract / start / duration) ──
    company = title = city = contract_type = start_month = duration = None
    posted_at_raw = None

    header = page.css("section.detail_offre article.w_75")
    if header:
        h = header[0]
        company       = (h.css("h2::text").get() or "").strip() or None
        title         = (h.css("h1::text").get() or "").strip() or None
        li_items      = [li.css("::text").get() or "" for li in h.css("ul li")]
        city          = li_items[0].strip() if len(li_items) > 0 else None
        contract_type = li_items[1].strip() if len(li_items) > 1 else None
        start_month   = li_items[2].strip() if len(li_items) > 2 else None
        duration      = li_items[3].strip() if len(li_items) > 3 else None
        posted_at_raw = _joined(h, "p::text")

    # ── Full location (country + city) from mission section ──
    # First span.d_block in any paragraph gives "PAYS (VILLE)" e.g. "ETATS-UNIS (HOUSTON -TX-)"
    location = None
    for span in page.css("p span.d_block"):
        text = (span.css("::text").get() or "").strip()
        if text and re.search(r"[A-Z]{3}", text):
            location = text
            break
    if not location:
        location = city  # fall back to city from the header list

    # ── Description and profile (both in p.pre-formatted) ──
    pre_sections = page.css("p.pre-formatted")
    description = _joined(pre_sections[0], "::text") if pre_sections else None
    profile     = _joined(pre_sections[1], "::text") if len(pre_sections) > 1 else None

    # ── Additional info section (reference, publication / expiration dates) ──
    reference  = None
    published_at = None
    expires_at = None

    info = page.css("article.fllwidth")
    if info:
        for span in info[0].css("span.d_block"):
            raw = " ".join(t.strip() for t in span.css("::text").getall() if t.strip())
            if not raw:
                continue
            if "REFERENCE" in raw.upper():
                reference = raw
            elif "publication" in raw.lower():
                published_at = _parse_french_date(raw) or raw
            elif "expiration" in raw.lower():
                expires_at = _parse_french_date(raw) or raw

    # Fall back to the short posted_at from the header if the full date wasn't found
    if not published_at and posted_at_raw:
        published_at = _parse_french_date(posted_at_raw) or posted_at_raw

    return {
        "url": url,
        "source": "mon_vie_via",
        "title": title,
        "company": company,
        "location": location,
        "contract_type": contract_type,
        "duration": duration,
        "start_month": start_month,
        "posted_at": published_at,
        "expires_at": expires_at,
        "description": description,
        "profile": profile,
        "reference": reference,
    }
