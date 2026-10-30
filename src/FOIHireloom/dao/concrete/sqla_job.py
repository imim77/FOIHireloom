from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, func, not_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.models.job import SEARCH_TITLE_WEIGHT
from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_page import JobPageTargetDTO
from FOIHireloom.dto.job_search import CategoryDTO, JobSearchCriteriaDTO
from FOIHireloom.dto.job_sync import JobSnapshotDTO
from FOIHireloom.dao.interfaces.job import JobRepository, JobSearchHit


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

    async def search(self, criteria: JobSearchCriteriaDTO) -> list[JobSearchHit]:
        title_match = None
        if criteria.terms:
            matches = Job.search_vector.bool_op("@@")
            title_match = matches(func.to_tsquery(
                "simple", " & ".join(f"{term}:*{SEARCH_TITLE_WEIGHT}" for term in criteria.terms)
            ))
        statement = select(Job, title_match).where(listed_condition(criteria.county_id))
        if criteria.terms:
            query = " & ".join(f"{term}:*" for term in criteria.terms)
            statement = statement.where(matches(func.to_tsquery("simple", query)))
        if criteria.category is not None:
            statement = statement.where(func.upper(Job.category) == func.upper(criteria.category))
        if criteria.open_on is not None:
            statement = statement.where(open_condition(criteria.open_on))
        if (after := criteria.after) is not None:
            if after.published_on is None:
                later = and_(Job.published_on.is_(None), Job.id < after.id)
            else:
                later = or_(
                    Job.published_on < after.published_on,
                    and_(Job.published_on == after.published_on, Job.id < after.id),
                    Job.published_on.is_(None),
                )
            if title_match is not None:
                later = or_(and_(title_match, later), not_(title_match)) if after.title_match else \
                    and_(not_(title_match), later)
            statement = statement.where(later)
        order = [Job.published_on.desc().nulls_last(), Job.id.desc()]
        if title_match is not None:
            order.insert(0, title_match.desc())
        statement = statement.order_by(*order).limit(criteria.limit)
        return [JobSearchHit(job, title_match) for job, title_match in await self._session.execute(statement)]

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

    async def list_page_candidates(self, retry_before: datetime, limit: int) -> list[JobPageTargetDTO]:
        statement = (
            select(Job.id, Job.canonical_url, Job.content_hash)
            .where(listed_condition(), page_due_condition(retry_before))
            .order_by(Job.published_on.desc().nulls_last(), Job.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [JobPageTargetDTO.model_validate(row) for row in result.all()]

    async def count_page_candidates(self, retry_before: datetime) -> int:
        statement = select(func.count()).select_from(Job).where(listed_condition(), page_due_condition(retry_before))
        return await self._session.scalar(statement)

    async def record_page(self, job_id: int, page: ParsedJobPageDTO, source_hash: str, checked_at: datetime) -> None:
        await self._session.execute(update(Job).where(Job.id == job_id).values(
            page_status="fetched", page_checked_at=checked_at, page_fetched_at=checked_at,
            page_source_hash=source_hash, page_error=None,
            **{f"page_{name}": value for name, value in page.model_dump().items()},
        ))

    async def record_page_problem(self, job_id: int, status: str, error: str, checked_at: datetime) -> None:
        if status not in {"unavailable", "failed"}:
            raise ValueError("A page problem is either 'unavailable' or 'failed'.")
        await self._session.execute(update(Job).where(Job.id == job_id).values(
            page_status=status, page_checked_at=checked_at, page_error=error,
        ))

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


def effective_deadline() -> ColumnElement[date]:
    """The closing date from the job page ("Natječaj vrijedi do"), else the feed's deadline."""
    return func.coalesce(Job.page_valid_until, Job.deadline_on)


def open_condition(open_on: date) -> ColumnElement[bool]:
    """True unless the job's known deadline is before open_on."""
    deadline = effective_deadline()
    return or_(deadline.is_(None), deadline >= open_on)


def page_due_condition(retry_before: datetime) -> ColumnElement[bool]:
    """True for jobs whose detail page was never fetched, is outdated, or may be retried."""
    return or_(
        Job.page_status == "pending",
        and_(Job.page_status == "fetched", Job.page_source_hash != Job.content_hash),
        and_(Job.page_status.in_(("unavailable", "failed")), Job.page_checked_at < retry_before),
    )
