from abc import ABC, abstractmethod
from collections.abc import Collection
from datetime import datetime

from FOIHireloom.db.models import JobFeedMembership
from FOIHireloom.dto.job_search import JobCountyDTO, JobListingDTO
from FOIHireloom.dto.job_sync import MembershipSnapshotDTO


class JobFeedMembershipRepository(ABC):
    """Access job membership in Croatian county and occupation feeds in the
    caller's transaction.

    Present and missing memberships remain available, including for disabled
    feeds. EU feed memberships are excluded. Listings and counties come from
    county feeds only. Missing from one feed does not imply that the job is
    closed or absent from other feeds.
    """

    @abstractmethod
    async def get_by_job_and_feed(
        self, job_id: int, feed_id: int
    ) -> JobFeedMembership | None:
        """Return the membership for this exact job/feed pair, or None if absent."""

    @abstractmethod
    async def list_for_feed(self, feed_id: int) -> list[JobFeedMembership]:
        """Return all memberships of the feed ordered by ascending job ID."""

    @abstractmethod
    async def list_listings(self, job_id: int) -> list[JobListingDTO]:
        """Return the job's present and missing county-feed memberships by county name."""

    @abstractmethod
    async def list_counties(self, job_ids: Collection[int]) -> list[JobCountyDTO]:
        """Return the counties of these jobs' county-feed memberships, present ones first."""

    @abstractmethod
    async def add(self, membership: JobFeedMembership) -> None:
        """Add and flush a membership without committing the transaction.

        The job and feed IDs must refer to records in the current transaction.
        A missing or EU feed raises ValueError before attachment.
        Database errors propagate; the caller owns rollback. Generated
        observation timestamps are available after the call.
        """

    @abstractmethod
    async def list_snapshots_for_feed(self, feed_id: int) -> list[MembershipSnapshotDTO]:
        """Return each membership's job ID and presence status for a feed."""

    @abstractmethod
    async def create_many(self, feed_id: int, job_ids: Collection[int], seen_at: datetime) -> None:
        """Add present memberships for these jobs; raise ValueError for a missing or EU feed."""

    @abstractmethod
    async def mark_present(self, feed_id: int, job_ids: Collection[int], seen_at: datetime) -> None:
        """Mark existing memberships of these jobs present at seen_at."""

    @abstractmethod
    async def mark_missing(self, feed_id: int, job_ids: Collection[int], missing_since: datetime) -> None:
        """Mark present memberships missing; already missing ones keep their time."""

    @abstractmethod
    async def touch_present(self, feed_id: int, seen_at: datetime) -> list[int]:
        """Confirm every present membership at seen_at; return their job IDs."""
