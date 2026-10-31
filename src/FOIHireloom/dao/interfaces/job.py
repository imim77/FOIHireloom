from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime
from typing import NamedTuple

from FOIHireloom.db.models import Job
from FOIHireloom.dto.category_snapshot import CategoryInputDTO
from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_market import JobMarketAggregatesDTO, JobMarketCriteriaDTO
from FOIHireloom.dto.job_page import JobPageTargetDTO
from FOIHireloom.dto.job_search import CategoryDTO, JobSearchCriteriaDTO
from FOIHireloom.dto.job_sync import CategoryEvidenceDTO, FilledCategoryDTO, JobSnapshotDTO


class JobSearchHit(NamedTuple):
    """A found job; title_match tells whether every search term matched its title, None without terms."""

    job: Job
    title_match: bool | None


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
    async def search(self, criteria: JobSearchCriteriaDTO) -> list[JobSearchHit]:
        """Return up to criteria.limit listed jobs matching every criterion.

        A job is listed while it is present in at least one county feed. With
        search terms, jobs whose title matches every term come first. Jobs
        are then ordered by publication date, newest first and unknown dates
        last, then by descending ID; criteria.after continues after that
        position.
        """

    @abstractmethod
    async def market_aggregates(self, criteria: JobMarketCriteriaDTO) -> JobMarketAggregatesDTO:
        """Count the listed jobs matching criteria, as search() would find them, by county and other fields."""

    @abstractmethod
    async def list_categories(self, open_on: date) -> list[CategoryDTO]:
        """Count listed jobs per category whose known deadline is not before open_on.

        Most common categories come first; jobs without a category are left out.
        """

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
        """Insert first-seen jobs and flush; return database IDs by source job ID.

        A category is recorded as coming from the job's description.
        """

    @abstractmethod
    async def update_content(self, jobs: Mapping[int, ParsedJobDTO], seen_at: datetime) -> None:
        """Replace the published content of these jobs, keyed by database ID.

        Marks them seen and changed at seen_at; availability and employer
        links are left alone. A category in the new content replaces the
        stored one, including one filled in from a feed; content without a
        category keeps the stored category and its source.
        """

    @abstractmethod
    async def mark_seen(self, job_ids: Collection[int], seen_at: datetime) -> None:
        """Record that these jobs were still published at seen_at."""

    @abstractmethod
    async def list_category_evidence(self, feed_id: int) -> list[CategoryEvidenceDTO]:
        """Return evidence for every job this feed lists or has listed that has
        no category from its own description, ordered by job ID.

        Each job's mappings come from all its occupation feeds, not only this one.
        """

    @abstractmethod
    async def list_category_inputs(self) -> list[CategoryInputDTO]:
        """Return the category fill's inputs and stored result for every listed job, ordered by job ID.

        Occupation feed IDs cover every presence and are ascending.
        """

    @abstractmethod
    async def set_feed_categories(self, categories: Mapping[int, FilledCategoryDTO | None]) -> None:
        """Store filled-in categories by job ID; None clears one.

        Jobs whose category comes from their description are left alone.
        """

    @abstractmethod
    async def list_page_candidates(self, retry_before: datetime, limit: int) -> list[JobPageTargetDTO]:
        """Return up to limit listed jobs whose detail page is due, newest publication first.

        A page is due when it was never fetched, was fetched for older feed
        content, or was unavailable or failed before retry_before.
        """

    @abstractmethod
    async def count_page_candidates(self, retry_before: datetime) -> int:
        """Count the listed jobs whose detail page is due, as list_page_candidates defines it."""

    @abstractmethod
    async def record_page(self, job_id: int, page: ParsedJobPageDTO, source_hash: str, checked_at: datetime) -> None:
        """Store a fetched detail page for the feed content with source_hash."""

    @abstractmethod
    async def record_page_problem(self, job_id: int, status: str, error: str, checked_at: datetime) -> None:
        """Mark a detail page check 'unavailable' or 'failed'; earlier fetched values stay."""
