from abc import ABC, abstractmethod

from models import JobOffer


class JobSource(ABC):
    """Abstract base class for all job data sources."""

    #: Set to False for sources that don't search by keyword (e.g. VIE portal).
    #: The pipeline will call fetch() once instead of once per keyword.
    uses_keywords: bool = True

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for this source (e.g. 'france_travail')."""
        ...

    @abstractmethod
    def fetch(self, keywords: str, location: str, max_results: int) -> list[JobOffer]:
        """
        Fetch job offers matching the given search parameters.

        Args:
            keywords: Search terms (e.g. "python développeur")
            location: Source-specific location identifier
            max_results: Upper bound on how many offers to return

        Returns:
            List of JobOffer instances.
        """
        ...
