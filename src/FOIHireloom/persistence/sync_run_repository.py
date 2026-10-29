from abc import ABC, abstractmethod

from FOIHireloom.db.models import SyncRun


class SyncRunRepository(ABC):
    """Access sync attempts for Croatian county feeds in the caller's transaction.

    Disabled county feeds retain their history. EU feed history is excluded.
    Persist failure outcomes in a separate transaction after rolling back import
    writes, so that the audit record survives the failed import.
    """

    @abstractmethod
    async def get_by_id(self, run_id: int) -> SyncRun | None:
        """Return a county feed's sync attempt by ID, or None if absent."""

    @abstractmethod
    async def get_latest_for_feed(self, feed_id: int) -> SyncRun | None:
        """Return the latest attempt of any status, or None if absent.

        Order by started_at descending, then by ID descending to break ties.
        """

    @abstractmethod
    async def add(self, sync_run: SyncRun) -> None:
        """Add and flush an attempt without committing the transaction.

        feed_id must identify an existing Croatian county feed in this
        transaction; otherwise raise ValueError before attaching the attempt.
        Generated fields are available afterwards. Database errors propagate;
        the caller owns rollback.
        """
