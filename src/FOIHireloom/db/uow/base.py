from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from FOIHireloom.dao.interfaces.county import CountyRepository
from FOIHireloom.dao.interfaces.job import JobRepository
from FOIHireloom.dao.interfaces.job_feed_membership import JobFeedMembershipRepository
from FOIHireloom.dao.interfaces.source_feed import SourceFeedRepository
from FOIHireloom.dao.interfaces.sync_run import SyncRunRepository


class UnitOfWork(ABC):
    """Own a repository transaction within an async context.

    Changes persist only after an explicit commit(). Exiting the context
    rolls back any remaining changes and releases the session, including
    when an exception escapes. Repositories are available only in the context.
    """

    @property
    @abstractmethod
    def counties(self) -> CountyRepository:
        """Return the county reference repository bound to the same session."""

    @property
    @abstractmethod
    def jobs(self) -> JobRepository:
        """Return the job repository bound to this context's session."""

    @property
    @abstractmethod
    def job_feed_memberships(self) -> JobFeedMembershipRepository:
        """Return the job/feed membership repository bound to the same session."""

    @property
    @abstractmethod
    def source_feeds(self) -> SourceFeedRepository:
        """Return the Croatian source feed repository bound to the same session."""

    @property
    @abstractmethod
    def sync_runs(self) -> SyncRunRepository:
        """Return the sync attempt repository bound to the same session."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Open a fresh session; an already active instance cannot be reentered."""

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work and close.

        Database errors escaping the context are re-raised as PersistenceError
        (ConflictError for constraint violations); others propagate unchanged.
        """

    @abstractmethod
    async def commit(self) -> None:
        """Persist the current transaction; database errors raise PersistenceError."""

    @abstractmethod
    async def rollback(self) -> None:
        """Discard the current transaction while keeping the context usable."""
