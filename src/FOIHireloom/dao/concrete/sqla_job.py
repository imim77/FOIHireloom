from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import Job, JobFeedMembership, SourceFeed
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_search import CategoryDTO, JobSearchCriteriaDTO
from FOIHireloom.dto.job_sync import JobSnapshotDTO
from FOIHireloom.dao.interfaces.job import JobRepository


class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: int) -> Job | None:
        return await self._session.get(Job, job_id)

    async def get_by_source_job_id(self, provider: str, source_job_id: str) -> Job | None:
        statement = select(Job).where(
            Job.provider == provider,
            Job.source_job_id == source_job_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_canonical_url(self, provider: str, canonical_url: str) -> Job | None:
        statement = select(Job).where(
            Job.provider == provider,
            Job.canonical_url == canonical_url,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def search(self, criteria: JobSearchCriteriaDTO) -> list[Job]:
        statement = select(Job).where(listed_condition(criteria.county_id))
        if criteria.terms:
            query = " & ".join(f"{term}:*" for term in criteria.terms)
            statement = statement.where(Job.search_vector.bool_op("@@")(func.to_tsquery("simple", query)))
        if criteria.category is not None:
            statement = statement.where(func.upper(Job.category) == func.upper(criteria.category))
        if criteria.open_on is not None:
            statement = statement.where(open_condition(criteria.open_on))
        if (after := criteria.after) is not None:
            if after.published_on is None:
                statement = statement.where(Job.published_on.is_(None), Job.id < after.id)
            else:
                statement = statement.where(or_(
                    Job.published_on < after.published_on,
                    and_(Job.published_on == after.published_on, Job.id < after.id),
                    Job.published_on.is_(None),
                ))
        statement = statement.order_by(Job.published_on.desc().nulls_last(), Job.id.desc()).limit(criteria.limit)
        return list(await self._session.scalars(statement))

    async def list_categories(self, open_on: date) -> list[CategoryDTO]:
        open_jobs = func.count().label("open_jobs")
        statement = (
            select(Job.category.label("name"), open_jobs)
            .where(Job.category.is_not(None), listed_condition(), open_condition(open_on))
            .group_by(Job.category)
            .order_by(open_jobs.desc(), Job.category)
        )
        result = await self._session.execute(statement)
        return [CategoryDTO.model_validate(row) for row in result.all()]

    async def add(self, job: Job) -> None:
        self._session.add(job)
        await self._session.flush()

    async def list_snapshots(self, provider: str, source_job_ids: Collection[str]) -> list[JobSnapshotDTO]:
        if not source_job_ids:
            return []
        statement = select(Job.id, Job.source_job_id, Job.content_hash).where(
            Job.provider == provider, Job.source_job_id.in_(source_job_ids)
        )
        result = await self._session.execute(statement)
        return [JobSnapshotDTO.model_validate(row) for row in result.all()]

    async def create_many(self, provider: str, jobs: Sequence[ParsedJobDTO], seen_at: datetime) -> dict[str, int]:
        entities = [
            Job(provider=provider, **self._content(job), first_seen_at=seen_at, last_seen_at=seen_at,
                content_changed_at=seen_at)
            for job in jobs
        ]
        self._session.add_all(entities)
        await self._session.flush()
        return {entity.source_job_id: entity.id for entity in entities}

    async def update_content(self, jobs: Mapping[int, ParsedJobDTO], seen_at: datetime) -> None:
        if jobs:
            await self._session.execute(update(Job), [
                {"id": job_id, **self._content(job), "last_seen_at": seen_at,
                 "content_changed_at": seen_at}
                for job_id, job in jobs.items()
            ])

    async def mark_seen(self, job_ids: Collection[int], seen_at: datetime) -> None:
        if job_ids:
            await self._session.execute(
                update(Job).where(Job.id.in_(job_ids)).values(last_seen_at=seen_at)
            )

    @staticmethod
    def _content(job: ParsedJobDTO) -> dict[str, object]:
        return job.model_dump() | {"quality_flags": list(job.quality_flags)}


def listed_condition(county_id: int | None = None) -> ColumnElement[bool]:
    """True for jobs present in a county feed, optionally of one county."""
    listed = (
        select(JobFeedMembership.job_id)
        .join(SourceFeed)
        .where(
            JobFeedMembership.job_id == Job.id,
            JobFeedMembership.presence_status == "present",
            SourceFeed.scope == "county",
        )
    )
    if county_id is not None:
        listed = listed.where(SourceFeed.county_id == county_id)
    return listed.exists()


def open_condition(open_on: date) -> ColumnElement[bool]:
    """True unless the job's known deadline is before open_on."""
    return or_(Job.deadline_on.is_(None), Job.deadline_on >= open_on)
