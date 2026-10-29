from abc import ABC, abstractmethod

from FOIHireloom.db.models import Job


class JobRepository(ABC):
    """Access job records within a transaction owned by the caller."""

    @abstractmethod
    async def get_by_id(self, job_id: int) -> Job | None:
        """Return the job with this database ID, or None if it is absent."""

    @abstractmethod
    async def get_by_source_job_id(self, provider: str, source_job_id: str) -> Job | None:
        """Look up a source's job ID within its provider's namespace."""

    @abstractmethod
    async def get_by_canonical_url(self, provider: str, canonical_url: str) -> Job | None:
        """Look up a canonical URL within its provider's namespace."""

    @abstractmethod
    async def add(self, job: Job) -> None:
        """Add and flush a job without committing the caller's transaction.

        Generated fields, including the ID, are available after the call.
        Database constraint errors propagate to the caller, who owns rollback.
        """
