from abc import ABC, abstractmethod
from datetime import datetime

from FOIHireloom.db.models import SyncRun
from FOIHireloom.dto.job_sync import SyncRunOutcomeDTO


class SyncRunRepository(ABC):
    """Access sync attempts for Croatian county and occupation feeds in the
    caller's transaction.

    Disabled feeds retain their history. EU feed history is excluded.
    Persist failure outcomes in a separate transaction after rolling back import
    writes, so that the audit record survives the failed import.
    """

    @abstractmethod
    async def get_by_id(self, run_id: int) -> SyncRun | None:
        """Return a county or occupation feed's sync attempt by ID, or None if absent."""

    @abstractmethod
    async def get_latest_for_feed(self, feed_id: int) -> SyncRun | None:
        """Return the latest attempt of any status, or None if absent.

        Order by started_at descending, then by ID descending to break ties.
        """

    @abstractmethod
    async def add(self, sync_run: SyncRun) -> None:
        """Add and flush an attempt without committing the transaction.

        feed_id must identify an existing county or occupation feed in this
        transaction; otherwise raise ValueError before attaching the attempt.
        Generated fields are available afterwards. Database errors propagate;
        the caller owns rollback.
        """

    @abstractmethod
    async def start(self, feed_id: int) -> int:
        """Add a running attempt started at the transaction time; return its ID."""

    @abstractmethod
    async def finish(self, run_id: int, outcome: SyncRunOutcomeDTO, finished_at: datetime) -> None:
        """Complete a running attempt; raise NotFoundError for an unknown ID."""

    @abstractmethod
    async def get_latest_items_seen(self, feed_id: int) -> int | None:
        """Return items_seen of the feed's latest succeeded attempt, or None."""
