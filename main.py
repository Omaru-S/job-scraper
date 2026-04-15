import argparse
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Suppress scrapling's per-request INFO logs (it uses a custom LoggerProxy, not stdlib)
from scrapling.core.utils import set_logger
_silent_logger = logging.getLogger("scrapling")
_silent_logger.setLevel(logging.WARNING)
set_logger(_silent_logger)

import config
from pipeline import run_pipeline
from api.france_travail import FranceTravailSource
from sources.welcome_to_the_jungle import WelcomeToTheJungleSource
from sources.mon_vie_via import MonVieViaSource

ALL_SOURCES = {
    "france_travail": FranceTravailSource,
    "welcome_to_the_jungle": WelcomeToTheJungleSource,
    "mon_vie_via": MonVieViaSource,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch job offers from multiple sources.")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=config.DEFAULT_KEYWORDS,
        help="One or more keyword searches (default: from .env DEFAULT_KEYWORDS)",
    )
    parser.add_argument(
        "--location",
        default=config.DEFAULT_LOCATION,
        help=f"Department code (default: '{config.DEFAULT_LOCATION}' = Paris). E.g. 69=Lyon, 13=Marseille. Leave empty for nationwide.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(ALL_SOURCES.keys()),
        default=list(ALL_SOURCES.keys()),
        help="Which sources to query (default: all)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=config.DEFAULT_MAX_RESULTS,
        dest="max_results",
        help=f"Max results per source (default: {config.DEFAULT_MAX_RESULTS})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources = [ALL_SOURCES[name]() for name in args.sources]
    run_pipeline(
        sources=sources,
        keywords=args.keywords,
        location=args.location,
        max_results=args.max_results,
    )


if __name__ == "__main__":
    main()
