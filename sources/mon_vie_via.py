from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from models import JobOffer
from scraping.mvv import CardResult, list_offers, scrape_offer
from sources.base import JobSource

_SCRAPE_WORKERS = 3  # concurrent Playwright sessions


class MonVieViaSource(JobSource):
    """
    Scraper for mon-vie-via.businessfrance.fr.

    This source is VIE/VIA only and country-scoped (Japan, USA, Singapore,
    Switzerland) so it ignores the pipeline's `keywords` and `location`
    parameters — the country filter is baked into the scraper.

    The pipeline calls fetch() once per keyword; we only do the real work on
    the first call and return [] for subsequent ones to avoid re-scraping the
    same listing page 10+ times.
    """

    def __init__(self) -> None:
        self._done = False

    @property
    def name(self) -> str:
        return "mon_vie_via"

    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        if self._done:
            return []
        self._done = True

        # max_clicks: each "Voir plus" click loads ~6 cards; default 100 → ~600 cards max
        # Pass max_results // 6 but with a generous floor so we don't stop too early
        max_clicks = max(20, max_results // 6)

        # 1. Listing page → filtered cards (clicks "Voir plus" until exhausted)
        cards: list[CardResult] = list_offers(max_clicks=max_clicks)

        # 2. Scrape detail pages in parallel
        offers: list[JobOffer] = []
        batch = cards[:max_results]
        futures: dict = {}

        with ThreadPoolExecutor(max_workers=_SCRAPE_WORKERS) as pool:
            for card in batch:
                futures[pool.submit(scrape_offer, card.url)] = card

            with tqdm(
                as_completed(futures),
                total=len(futures),
                desc="  Scraping",
                unit="page",
                leave=False,
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
        experience=None,  # MVV offers rarely specify experience requirements
    )
