import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from models import JobOffer
from scraping.mvv import CardResult, list_offers, scrape_offer
from sources.base import JobSource

_SCRAPE_WORKERS = 3  # concurrent Playwright sessions

# Maps the French country prefix in card locations to a display label
_COUNTRY_LABELS = {
    "ETATS-UNIS": "États-Unis",
    "JAPON":      "Japon",
    "SINGAPOUR":  "Singapour",
    "SUISSE":     "Suisse",
}


def _country_key(location: str | None) -> str:
    loc = (location or "").upper()
    for key in _COUNTRY_LABELS:
        if key in loc:
            return key
    return "AUTRE"


class MonVieViaSource(JobSource):
    """
    Scraper for mon-vie-via.businessfrance.fr.

    Fetches all VIE/VIA offers in Japan, USA, Singapore and Switzerland
    using the site's own country filter — no keyword search needed.
    """

    uses_keywords = False

    @property
    def name(self) -> str:
        return "mon_vie_via"

    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        # 1. Listing page — click "Voir plus" until the button disappears
        print("  Fetching listing…")
        cards: list[CardResult] = list_offers()

        # 2. Show per-country breakdown
        counts: Counter = Counter(_country_key(c.location) for c in cards)
        for key, label in _COUNTRY_LABELS.items():
            n = counts.get(key, 0)
            print(f"  {label:<12} {n:>3} offer{'s' if n != 1 else ''} found")
        print(f"  {'Total':<12} {len(cards):>3} offers")

        # 3. Scrape all detail pages in parallel (no max_results cap — we want everything)
        offers: list[JobOffer] = []
        futures: dict = {}

        with ThreadPoolExecutor(max_workers=_SCRAPE_WORKERS) as pool:
            for card in cards:
                futures[pool.submit(scrape_offer, card.url)] = card

            with tqdm(
                as_completed(futures),
                total=len(futures),
                desc="  Scraping",
                unit="page",
                leave=True,
            ) as bar:
                for future in bar:
                    card = futures[future]
                    bar.set_postfix_str(
                        f"{card.company or '?'} — {(card.title or '')[:30]}"
                    )
                    try:
                        offers.append(_map(future.result()))
                    except Exception as exc:
                        tqdm.write(f"  ! Skipped {card.url}: {exc}")

        return offers


def _map(data: dict) -> JobOffer:
    return JobOffer(
        title=data["title"] or "",
        company=data["company"],
        location=data["location"] or "",
        url=data["url"],
        source=data["source"],
        posted_at=data.get("posted_at"),
        description=data.get("description"),
        contract_type=data.get("contract_type"),
        experience=None,
    )
