from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from FOIHireloom.persistence.job_repository import JobRepository
from FOIHireloom.persistence.source_feed_repository import SourceFeedRepository


class UnitOfWork(ABC):
    """Own a repository transaction within an async context.

    Changes persist only after an explicit commit(). Exiting the context
    rolls back any remaining changes and releases the session, including
    when an exception escapes. Repositories are available only in the context.
    """

    @property
    @abstractmethod
    def jobs(self) -> JobRepository:
        """Return the job repository bound to this context's session."""

    @property
    @abstractmethod
    def source_feeds(self) -> SourceFeedRepository:
        """Return the Croatian source feed repository bound to the same session."""

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
        """Roll back uncommitted work and close without suppressing exceptions."""

    @abstractmethod
    async def commit(self) -> None:
        """Persist the current transaction; database errors propagate to the caller."""

    @abstractmethod
    async def rollback(self) -> None:
        """Discard the current transaction while keeping the context usable."""
