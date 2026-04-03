from llm.enricher import enrich_offers
from core.filters import _contract_allowed, _experience_allowed, apply_filters
from models import JobOffer
from sources.base import JobSource
from storage.json_writer import write_results


def _pre_filter(offers: list[JobOffer]) -> list[JobOffer]:
    """Drop offers that are already clearly rejected based on fields the API already provided.
    Fields that are None are left alone — the enricher may fill them later."""
    kept = []
    dropped = 0
    for offer in offers:
        if offer.contract_type is not None and not _contract_allowed(offer):
            dropped += 1
            continue
        if offer.experience is not None and not _experience_allowed(offer):
            dropped += 1
            continue
        kept.append(offer)
    if dropped:
        print(f"Pre-filter: dropped {dropped} obviously rejected offers ({len(kept)} remaining)")
    return kept


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

    print(f"Total fetched (with duplicates): {len(all_offers)}")

    seen: set[str] = set()
    unique_offers: list[JobOffer] = []
    for offer in all_offers:
        if offer.url and offer.url not in seen:
            seen.add(offer.url)
            unique_offers.append(offer)

    print(f"After deduplication: {len(unique_offers)} offers")

    unique_offers = _pre_filter(unique_offers)
    enrich_offers(unique_offers)

    print("Applying filters...")
    filtered = apply_filters(unique_offers)
    print(f"After filters: {len(filtered)}/{len(unique_offers)} offers kept")

    output_path = write_results(filtered)
    print(f"Results written to: {output_path}")
    return output_path
