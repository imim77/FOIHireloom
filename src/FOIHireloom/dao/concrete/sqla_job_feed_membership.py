from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import County, JobFeedMembership, SourceFeed
from FOIHireloom.dao.interfaces.job_feed_membership import JobFeedMembershipRepository
from FOIHireloom.dto.job_search import JobCountyDTO, JobListingDTO
from FOIHireloom.dto.job_sync import MembershipSnapshotDTO


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

    async def list_listings(self, job_id: int) -> list[JobListingDTO]:
        statement = (
            select(
                County.code.label("county_code"),
                County.name.label("county_name"),
                JobFeedMembership.presence_status,
                JobFeedMembership.first_seen_at,
                JobFeedMembership.last_seen_at,
                JobFeedMembership.missing_since_at,
                SourceFeed.last_success_at.label("feed_last_success_at"),
            )
            .select_from(JobFeedMembership)
            .join(SourceFeed)
            .join(County)
            .where(JobFeedMembership.job_id == job_id, SourceFeed.scope == "county")
            .order_by(County.name, SourceFeed.id)
        )
        result = await self._session.execute(statement)
        return [JobListingDTO.model_validate(row) for row in result.all()]

    async def list_counties(self, job_ids: Collection[int]) -> list[JobCountyDTO]:
        if not job_ids:
            return []
        statement = (
            select(
                JobFeedMembership.job_id,
                County.code.label("county_code"),
                County.name.label("county_name"),
                JobFeedMembership.presence_status,
            )
            .select_from(JobFeedMembership)
            .join(SourceFeed)
            .join(County)
            .where(JobFeedMembership.job_id.in_(job_ids), SourceFeed.scope == "county")
            .order_by(JobFeedMembership.job_id, JobFeedMembership.presence_status != "present", County.name)
        )
        result = await self._session.execute(statement)
        return [JobCountyDTO.model_validate(row) for row in result.all()]

    async def add(self, membership: JobFeedMembership) -> None:
        await self._require_county_feed(membership.feed_id)
        self._session.add(membership)
        await self._session.flush()

    async def list_snapshots_for_feed(self, feed_id: int) -> list[MembershipSnapshotDTO]:
        statement = (
            select(JobFeedMembership.job_id, JobFeedMembership.presence_status)
            .join(SourceFeed)
            .where(JobFeedMembership.feed_id == feed_id, SourceFeed.scope == "county")
            .order_by(JobFeedMembership.job_id)
        )
        result = await self._session.execute(statement)
        return [MembershipSnapshotDTO.model_validate(row) for row in result.all()]

    async def create_many(self, feed_id: int, job_ids: Collection[int], seen_at: datetime) -> None:
        if not job_ids:
            return
        await self._require_county_feed(feed_id)
        self._session.add_all([
            JobFeedMembership(job_id=job_id, feed_id=feed_id, first_seen_at=seen_at, last_seen_at=seen_at)
            for job_id in job_ids
        ])
        await self._session.flush()

    async def mark_present(self, feed_id: int, job_ids: Collection[int], seen_at: datetime) -> None:
        if job_ids:
            await self._session.execute(
                update(JobFeedMembership)
                .where(JobFeedMembership.feed_id == feed_id, JobFeedMembership.job_id.in_(job_ids))
                .values(presence_status="present", last_seen_at=seen_at, missing_since_at=None)
            )

    async def mark_missing(self, feed_id: int, job_ids: Collection[int], missing_since: datetime) -> None:
        if job_ids:
            await self._session.execute(
                update(JobFeedMembership)
                .where(JobFeedMembership.feed_id == feed_id, JobFeedMembership.job_id.in_(job_ids),
                       JobFeedMembership.presence_status == "present")
                .values(presence_status="missing", missing_since_at=missing_since)
            )

    async def touch_present(self, feed_id: int, seen_at: datetime) -> list[int]:
        result = await self._session.execute(
            update(JobFeedMembership)
            .where(JobFeedMembership.feed_id == feed_id, JobFeedMembership.presence_status == "present")
            .values(last_seen_at=seen_at)
            .returning(JobFeedMembership.job_id)
        )
        return sorted(result.scalars().all())

    async def _require_county_feed(self, feed_id: int) -> None:
        found = await self._session.scalar(select(SourceFeed.id).where(
            SourceFeed.id == feed_id,
            SourceFeed.scope == "county",
        ))
        if found is None:
            raise ValueError("Memberships require an existing Croatian county source feed.")
