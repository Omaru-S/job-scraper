"""
WTTJ scraping test harness.

Scrapes each URL in TEST_URLS and writes results to test.json at the project root.
Re-running updates existing entries (matched by URL) and appends new ones.

Usage:
    uv run python -m scraping.wttj.test_offers
"""

import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from scraping.wttj import scrape_job

TEST_URLS = [
    "https://www.welcometothejungle.com/fr/companies/datatorii/jobs/data-engineer-h-f_paris",
    "https://www.welcometothejungle.com/fr/companies/exalt/jobs/ingenieur-devops-cloud_paris_EXALT_jmr61YQ",
    "https://www.welcometothejungle.com/fr/companies/galadrim/jobs/software-engineer-full-stack-freelance",
]

OUTPUT = Path(__file__).resolve().parents[2] / "test.json"


def main() -> None:
    existing: dict[str, dict] = {}
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        existing = {entry["url"]: entry for entry in data}

    for url in TEST_URLS:
        print(f"Scraping: {url}")
        try:
            result = scrape_job(url)
            existing[url] = result
            print(f"  ✓ {result['title']} @ {result['company']} ({result['location']})")
            print(f"    Contract: {result['contract_type']} | Remote: {result['remote_type']}")
            print(f"    Salary: {result['salary_raw']} ({result['salary_min']} – {result['salary_max']})")
            print(f"    Experience: {result['experience']} | Education: {result['education']}")
        except Exception as exc:
            print(f"  ✗ Failed: {exc}")

    OUTPUT.write_text(
        json.dumps(list(existing.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {len(existing)} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
