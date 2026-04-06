import os

_SEEN_URLS_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "seen_urls.txt")


def _path() -> str:
    return os.path.abspath(_SEEN_URLS_PATH)


def load_seen_urls() -> set[str]:
    """Load the persisted set of already-seen URLs. Returns empty set if file doesn't exist."""
    p = _path()
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_seen_urls(urls: set[str]) -> None:
    """Persist the full set of seen URLs, one per line."""
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(url + "\n")
