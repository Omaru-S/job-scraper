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

URL = "https://www.welcometothejungle.com/fr/companies/safran-ai/jobs/deep-learning-scientist-acoustics-h-f_paris"


def _click_voir_plus(pw_page) -> None:
    """Click the view-more-btn inside the description section."""
    btn = pw_page.locator(
        '[data-testid="job-section-description"] [data-testid="view-more-btn"]'
    ).first
    if btn.count() and btn.is_visible():
        print("\n[page_action] Clicking view-more-btn…")
        btn.click()
        pw_page.wait_for_load_state("networkidle")
        print("[page_action] Done.")
    else:
        print("\n[page_action] view-more-btn not found or not visible.")


def _text(el, selector: str) -> str | None:
    parts = el.css(f"{selector}::text").getall()
    result = " ".join(p.strip() for p in parts if p.strip())
    return result or None


def main() -> None:
    print(f"Fetching: {URL}\n")
    page = DynamicFetcher.fetch(URL, network_idle=True, headless=True, page_action=_click_voir_plus)

    desc_nodes = page.css('[data-testid="job-section-description"] *::text').getall()
    description = " ".join(t.strip() for t in desc_nodes if t.strip()) or None
    tail = (description or "")[-200:]
    print(f"\nDescription tail:\n{tail}")

    print("\n--- data-testid elements ---")
    for el in page.css("[data-testid]"):
        testid = el.attrib.get("data-testid", "")
        text = " ".join(t.strip() for t in el.css("*::text").getall() if t.strip())[:100]
        if text:
            print(f"  [{testid}] {text}")


if __name__ == "__main__":
    main()
