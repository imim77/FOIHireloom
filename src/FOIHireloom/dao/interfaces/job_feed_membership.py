from abc import ABC, abstractmethod

from FOIHireloom.db.models import JobFeedMembership


class JobFeedMembershipRepository(ABC):
    """Access job membership in Croatian county feeds in the caller's transaction.

    Present and missing memberships remain available, including for disabled
    county feeds. EU feed memberships are excluded. Missing from one feed does
    not imply that the job is closed or absent from other feeds.
    """

    @abstractmethod
    async def get_by_job_and_feed(
        self, job_id: int, feed_id: int
    ) -> JobFeedMembership | None:
        """Return the membership for this exact job/feed pair, or None if absent."""

    @abstractmethod
    async def list_for_feed(self, feed_id: int) -> list[JobFeedMembership]:
        """Return all county-feed memberships ordered by ascending job ID."""

    @abstractmethod
    async def add(self, membership: JobFeedMembership) -> None:
        """Add and flush a membership without committing the transaction.

        The job and feed IDs must refer to records in the current transaction.
        A missing or non-county feed raises ValueError before attachment.
        Database errors propagate; the caller owns rollback. Generated
        observation timestamps are available after the call.
        """
