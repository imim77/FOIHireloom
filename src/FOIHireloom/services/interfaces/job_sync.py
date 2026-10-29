from abc import ABC, abstractmethod

from FOIHireloom.dto.job_sync import FeedSyncResultDTO, JobSyncResultDTO


class JobSyncServiceInterface(ABC):
    """Import HZZ job advertisements from the registered Croatian county feeds."""

    @abstractmethod
    async def sync_all(self) -> JobSyncResultDTO:
        """Sync every enabled county feed, one transaction per feed.

        A failed or rejected feed keeps its previous data and does not stop the
        others; each attempt is recorded in sync_runs.
        """

    @abstractmethod
    async def sync_feed(self, feed_id: int) -> FeedSyncResultDTO:
        """Sync one county feed, enabled or not; raise NotFoundError if it is unknown."""
