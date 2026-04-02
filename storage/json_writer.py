import json
import os
from dataclasses import asdict
from datetime import datetime

from models import JobOffer

_RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def write_results(offers: list[JobOffer]) -> str:
    """Write offers to a timestamped JSON file. Returns the output path."""
    results_dir = os.path.abspath(_RESULTS_DIR)
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(results_dir, f"jobs_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(offer) for offer in offers], f, ensure_ascii=False, indent=2)

    return filepath
