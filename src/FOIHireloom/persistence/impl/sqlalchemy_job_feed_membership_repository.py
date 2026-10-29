from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import JobFeedMembership, SourceFeed
from FOIHireloom.persistence.job_feed_membership_repository import JobFeedMembershipRepository


class SqlAlchemyJobFeedMembershipRepository(JobFeedMembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_job_and_feed(
        self, job_id: int, feed_id: int
    ) -> JobFeedMembership | None:
        statement = select(JobFeedMembership).join(SourceFeed).where(
            JobFeedMembership.job_id == job_id,
            JobFeedMembership.feed_id == feed_id,
            SourceFeed.scope == "county",
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_feed(self, feed_id: int) -> list[JobFeedMembership]:
        statement = (
            select(JobFeedMembership)
            .join(SourceFeed)
            .where(JobFeedMembership.feed_id == feed_id, SourceFeed.scope == "county")
            .order_by(JobFeedMembership.job_id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def add(self, membership: JobFeedMembership) -> None:
        feed_id = await self._session.scalar(select(SourceFeed.id).where(
            SourceFeed.id == membership.feed_id,
            SourceFeed.scope == "county",
        ))
        if feed_id is None:
            raise ValueError("Memberships require an existing Croatian county source feed.")
        self._session.add(membership)
        await self._session.flush()
