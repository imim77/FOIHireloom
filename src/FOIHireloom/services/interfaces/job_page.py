from abc import ABC, abstractmethod

from FOIHireloom.dto.job_page import JobPageFetchResultDTO


class JobPageServiceInterface(ABC):
    """Enrich listed jobs with the fields of their HZZ detail pages."""

    @abstractmethod
    async def fetch_due(self, limit: int) -> JobPageFetchResultDTO:
        """Fetch up to limit due pages, newest jobs first, one request at a time.

        Each page is stored in its own transaction as soon as it is read, and
        no transaction is open while a page downloads. The run stops early
        after repeated failed downloads. Raise ValueError for a limit below 1.
        """
