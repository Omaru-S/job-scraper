import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from models import JobOffer

_TRACKER_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "tracker.json")


def _path() -> str:
    return os.path.abspath(_TRACKER_PATH)


def _load() -> list[dict]:
    p = _path()
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def append_to_tracker(offers: list[JobOffer]) -> str:
    """
    Append new offers to results/tracker.json, tagging each with a scraped_at timestamp.
    Returns the tracker path.
    """
    existing = _load()
    scraped_at = datetime.now(timezone.utc).isoformat()

    new_entries = []
    for offer in offers:
        entry = asdict(offer)
        entry["scraped_at"] = scraped_at
        new_entries.append(entry)

    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(existing + new_entries, f, ensure_ascii=False, indent=2)

    return _path()
