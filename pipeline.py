from filters import apply_filters
from models import JobOffer
from sources.base import JobSource
from storage.json_writer import write_results


def run_pipeline(
    sources: list[JobSource],
    keywords: list[str],
    location: str,
    max_results: int,
) -> str:
    """Run all sources × keyword sets, deduplicate, filter, write results. Returns output path."""
    all_offers: list[JobOffer] = []

    for source in sources:
        for kw in keywords:
            print(f"[{source.name}] Fetching '{kw}'...")
            try:
                offers = source.fetch(kw, location, max_results)
                print(f"[{source.name}] '{kw}' -> {len(offers)} offers.")
                all_offers.extend(offers)
            except Exception as exc:
                print(f"[{source.name}] '{kw}' ERROR: {exc}")

    seen: set[str] = set()
    unique_offers: list[JobOffer] = []
    for offer in all_offers:
        if offer.url and offer.url not in seen:
            seen.add(offer.url)
            unique_offers.append(offer)

    filtered = apply_filters(unique_offers)
    print(f"After dedup: {len(unique_offers)} | After filters: {len(filtered)}")

    output_path = write_results(filtered)
    print(f"Results written to: {output_path}")
    return output_path
