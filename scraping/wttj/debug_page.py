"""
Single-page debug script for inspecting a WTTJ job listing.

Useful for checking selectors or verifying what data is available on a page
before updating scraper.py.

Usage:
    uv run python -m scraping.wttj.debug_page
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from scrapling.fetchers import DynamicFetcher

URL = "https://www.welcometothejungle.com/fr/companies/datatorii/jobs/data-engineer-h-f_paris"


def _text(el, selector: str) -> str | None:
    parts = el.css(f"{selector}::text").getall()
    result = " ".join(p.strip() for p in parts if p.strip())
    return result or None


def main() -> None:
    import re
    print(f"Fetching: {URL}\n")
    page = DynamicFetcher.fetch(URL, network_idle=True, headless=True)

    meta = page.css('[data-testid="job-metadata-block"]')
    title = meta.css("h2::text").get() if meta else page.css("h2::text").get()
    company = meta.css('a[href*="/fr/companies/"] span::text').get() if meta else None

    all_tokens = [t.strip() for t in meta.css("*::text").getall() if t.strip()] if meta else []

    print(f"Title:   {title}")
    print(f"Company: {company}")
    print(f"Tokens:  {all_tokens}")

    print("\n--- data-testid elements ---")
    for el in page.css("[data-testid]"):
        testid = el.attrib.get("data-testid", "")
        text = " ".join(t.strip() for t in el.css("*::text").getall() if t.strip())[:100]
        if text:
            print(f"  [{testid}] {text}")


if __name__ == "__main__":
    main()
