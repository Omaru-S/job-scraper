from tqdm import tqdm

from llm.enricher import enrich_offers
from core.filters import _contract_allowed, _experience_allowed, apply_filters
from core.validator import validate_offers
from models import JobOffer
from sources.base import JobSource
from storage.tracker import append_to_tracker
from storage.seen_urls import load_seen_urls, save_seen_urls


def _pre_filter(offers: list[JobOffer]) -> list[JobOffer]:
    kept, dropped = [], 0
    for offer in offers:
        if offer.contract_type is not None and not _contract_allowed(offer):
            dropped += 1
            continue
        if offer.experience is not None and not _experience_allowed(offer):
            dropped += 1
            continue
        kept.append(offer)
    if dropped:
        tqdm.write(f"  Pre-filter: dropped {dropped} obvious rejects ({len(kept)} remaining)")
    return kept


def run_pipeline(
    sources: list[JobSource],
    keywords: list[str],
    location: str,
    max_results: int,
) -> str:
    all_offers: list[JobOffer] = []

    for source in sources:
        print(f"\n── {source.name} ──────────────────────────")
        with tqdm(keywords, unit="keyword", leave=True) as bar:
            for kw in bar:
                bar.set_description(f"  {kw[:40]}")
                try:
                    offers = source.fetch(kw, location, max_results)
                    tqdm.write(f"  ✓ {kw!r:35} → {len(offers)} offers")
                    all_offers.extend(offers)
                except Exception as exc:
                    tqdm.write(f"  ✗ {kw!r:35} → ERROR: {exc}")

    print(f"\n── Pipeline ────────────────────────────────")
    print(f"  Fetched:  {len(all_offers)} total")

    seen_urls = load_seen_urls()
    unique_offers: list[JobOffer] = []
    for offer in all_offers:
        if offer.url and offer.url not in seen_urls:
            seen_urls.add(offer.url)
            unique_offers.append(offer)

    deduped = len(all_offers) - len(unique_offers)
    print(f"  Unique:   {len(unique_offers)} new  ({deduped} already seen)")

    unique_offers = _pre_filter(unique_offers)
    enrich_offers(unique_offers)

    filtered, reasons = apply_filters(unique_offers)
    reason_summary = "  ".join(f"{r}:{n}" for r, n in sorted(reasons.items()) if n)
    print(f"  Filtered: {len(unique_offers) - len(filtered)} dropped  ({reason_summary})")
    print(f"  Kept:     {len(filtered)}")

    validate_offers(filtered)

    output_path = append_to_tracker(filtered)
    save_seen_urls(seen_urls)

    print(f"\n  Results → {output_path}")
    return output_path
