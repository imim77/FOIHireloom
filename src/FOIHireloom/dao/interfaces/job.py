from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime

from FOIHireloom.db.models import Job
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_sync import JobSnapshotDTO


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

    @abstractmethod
    async def list_snapshots(self, provider: str, source_job_ids: Collection[str]) -> list[JobSnapshotDTO]:
        """Return the ID and content hash of every listed job that exists."""

    @abstractmethod
    async def create_many(self, provider: str, jobs: Sequence[ParsedJobDTO], seen_at: datetime) -> dict[str, int]:
        """Insert first-seen jobs and flush; return database IDs by source job ID."""

    @abstractmethod
    async def update_content(self, jobs: Mapping[int, ParsedJobDTO], seen_at: datetime) -> None:
        """Replace the published content of these jobs, keyed by database ID.

        Marks them seen and changed at seen_at; availability and employer
        links are left alone.
        """

    @abstractmethod
    async def mark_seen(self, job_ids: Collection[int], seen_at: datetime) -> None:
        """Record that these jobs were still published at seen_at."""
