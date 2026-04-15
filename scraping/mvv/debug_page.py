"""
Debug helper — fetches an MVV page with Playwright and dumps its structure.

Run with:
    uv run python -m scraping.mvv.debug_page
    uv run python -m scraping.mvv.debug_page --list
"""
import sys
import argparse

sys.stdout.reconfigure(encoding="utf-8")

from scrapling.fetchers import DynamicFetcher

OFFER_URL = "https://mon-vie-via.businessfrance.fr/offres/237615"
LIST_URL  = "https://mon-vie-via.businessfrance.fr/offres"


def dump_offer(url: str) -> None:
    print(f"\n{'='*60}")
    print(f"OFFER DETAIL: {url}")
    print('='*60)
    page = DynamicFetcher.fetch(url, network_idle=True, headless=True)

    print("\n--- All elements with visible text (tag / class / text) ---")
    for el in page.css("*"):
        own_text = (el.css("::text").get() or "").strip()
        if not own_text:
            continue
        tag = el.tag
        cls = (el.attrib.get("class") or "")[:60]
        print(f"  <{tag}> .{cls}")
        print(f"    → {own_text[:120]}")

    print("\n--- All href links ---")
    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        text = (a.css("::text").get() or "").strip()
        print(f"  {href!r:60} {text[:60]}")

    print("\n--- Page title ---")
    print(" ", page.css("title::text").get())


def dump_list(url: str) -> None:
    print(f"\n{'='*60}")
    print(f"LISTING PAGE: {url}")
    print('='*60)
    page = DynamicFetcher.fetch(url, network_idle=True, headless=True)

    print("\n--- All /offres/* links found ---")
    import re
    seen = set()
    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        if re.search(r"/offres/\d+", href) and href not in seen:
            seen.add(href)
            text = " ".join(t.strip() for t in a.css("*::text").getall() if t.strip())
            print(f"  {href}  |  {text[:80]}")
    print(f"\n  Total offer links: {len(seen)}")

    print("\n--- Top-level text blocks (likely cards or filters) ---")
    for el in page.css("[class]"):
        texts = [t.strip() for t in el.css("::text").getall() if t.strip()]
        if 3 <= len(texts) <= 20:
            cls = (el.attrib.get("class") or "")[:60]
            print(f"  .{cls}")
            print(f"    {' | '.join(texts[:10])}")

    print("\n--- Current URL after JS render ---")
    # scrapling doesn't expose the final URL directly, but we can note the input
    print(f"  (fetched: {url})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="Dump listing page instead of offer detail")
    parser.add_argument("--url", default=None, help="Override URL to fetch")
    args = parser.parse_args()

    if args.list:
        dump_list(args.url or LIST_URL)
    else:
        dump_offer(args.url or OFFER_URL)


if __name__ == "__main__":
    main()
