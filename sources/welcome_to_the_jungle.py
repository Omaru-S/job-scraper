from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from models import JobOffer
from scraping.wttj import CardResult, scrape_job, search_jobs
from sources.base import JobSource

_SCRAPE_WORKERS = 3  # concurrent Playwright sessions

# WTTJ uses city names, not department codes — map the most common ones.
_DEPT_TO_CITY: dict[str, str] = {
    "75": "Paris",
    "69": "Lyon",
    "13": "Marseille",
    "31": "Toulouse",
    "33": "Bordeaux",
    "59": "Lille",
    "06": "Nice",
    "67": "Strasbourg",
    "44": "Nantes",
    "34": "Montpellier",
}


class WelcomeToTheJungleSource(JobSource):

    @property
    def name(self) -> str:
        return "welcome_to_the_jungle"

    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        city = _DEPT_TO_CITY.get(location, location)

        # 1. Search pages → cards
        max_pages = max(1, max_results // 30)
        cards: list[CardResult] = search_jobs(keywords, city, max_pages=max_pages)

        # 2. Scrape detail pages in parallel
        offers: list[JobOffer] = []
        batch = cards[:max_results]
        futures = {}
        with ThreadPoolExecutor(max_workers=_SCRAPE_WORKERS) as pool:
            for card in batch:
                futures[pool.submit(scrape_job, card.url)] = card

            with tqdm(as_completed(futures), total=len(futures), desc="  Scraping", unit="page", leave=False) as bar:
                for future in bar:
                    card = futures[future]
                    bar.set_postfix_str(f"{card.company or '?'} — {(card.title or '')[:30]}")
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
        salary_min=data.get("salary_min"),
        salary_max=data.get("salary_max"),
        remote_type=data.get("remote_type"),
        experience=data.get("experience"),
    )
