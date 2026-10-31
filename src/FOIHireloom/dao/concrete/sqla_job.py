from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import CTE, ColumnElement, and_, bindparam, case, func, not_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.models.job import SEARCH_TITLE_WEIGHT
from FOIHireloom.dto.category_snapshot import CategoryInputDTO
from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_conditions import JobConditionsDTO, JobConditionsInputDTO, RawJobConditionsDTO
from FOIHireloom.dto.job_market import (
    MARKET_WINDOW_DAYS,
    CountyMarketCountDTO,
    JobMarketAggregatesDTO,
    JobMarketCriteriaDTO,
    MarketCountDTO,
)
from FOIHireloom.dto.job_page import JobPageTargetDTO
from FOIHireloom.dto.job_search import CategoryDTO, JobFilterCriteriaDTO, JobSearchCriteriaDTO
from FOIHireloom.dto.job_sync import CategoryEvidenceDTO, FilledCategoryDTO, JobSnapshotDTO
from FOIHireloom.dao.interfaces.job import JobRepository, JobSearchHit

# Columns by JobConditionsDTO field, and the page columns by RawJobConditionsDTO field.
STORED_CONDITIONS = {
    name: getattr(Job, "conditions_unrecognised" if name == "unrecognised" else name)
    for name in JobConditionsDTO.model_fields
}
PAGE_CONDITIONS = {name: getattr(Job, f"page_{name}") for name in RawJobConditionsDTO.model_fields}


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
        title_match = terms_condition(criteria.terms, SEARCH_TITLE_WEIGHT) if criteria.terms else None
        statement = select(Job, title_match).where(*filter_conditions(criteria))
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

    async def market_aggregates(self, criteria: JobMarketCriteriaDTO) -> JobMarketAggregatesDTO:
        found = (
            select(
                Job.id, Job.category, Job.category_source, Job.published_on, effective_deadline().label("deadline"),
                Job.page_fetched_at, Job.page_workers_needed.label("workers"), Job.page_education, Job.page_experience,
                Job.page_employer_name, Job.page_employment_type, Job.page_working_hours, Job.page_accommodation,
            )
            .where(*filter_conditions(criteria))
            .cte("found")
        )
        window_end = criteria.today + timedelta(days=MARKET_WINDOW_DAYS - 1)
        totals = (await self._session.execute(select(
            func.count(),
            func.count().filter(found.c.page_fetched_at.is_not(None)),
            func.count().filter(found.c.category_source == "description"),
            func.count().filter(found.c.category_source == "feed"),
            func.coalesce(func.sum(found.c.workers), 0),
            func.count().filter(found.c.published_on > criteria.today - timedelta(days=MARKET_WINDOW_DAYS)),
            func.count().filter(found.c.deadline.between(criteria.today, window_end)),
        ))).one()
        return JobMarketAggregatesDTO(
            jobs=totals[0], with_details=totals[1], with_category=totals[2] + totals[3],
            category_from_description=totals[2], category_from_feed=totals[3], workers_needed=totals[4],
            published_recently=totals[5], closing_soon=totals[6],
            counties=await self._county_counts(found),
            categories=await self._value_counts(found, found.c.category),
            employers=await self._value_counts(found, found.c.page_employer_name, criteria.top),
            employment_types=await self._value_counts(found, found.c.page_employment_type, listed=True),
            working_hours=await self._value_counts(found, found.c.page_working_hours, criteria.top),
            education=await self._value_counts(found, found.c.page_education, listed=True),
            experience=await self._value_counts(found, found.c.page_experience, criteria.top),
            accommodation=await self._value_counts(found, found.c.page_accommodation),
        )

    async def _county_counts(self, found: CTE) -> tuple[CountyMarketCountDTO, ...]:
        # A job listed by two feeds of one county counts once.
        placed = (
            select(JobFeedMembership.job_id, SourceFeed.county_id)
            .join(SourceFeed)
            .where(JobFeedMembership.presence_status == "present", SourceFeed.scope == "county",
                   JobFeedMembership.job_id.in_(select(found.c.id)))
            .distinct()
            .subquery()
        )
        jobs = func.count().label("jobs")
        statement = (
            select(County.code, County.name, jobs, func.coalesce(func.sum(found.c.workers), 0).label("workers_needed"))
            .select_from(placed)
            .join(County, County.id == placed.c.county_id)
            .join(found, found.c.id == placed.c.job_id)
            .group_by(County.id)
            .order_by(jobs.desc(), County.name)
        )
        return tuple(CountyMarketCountDTO.model_validate(row) for row in (await self._session.execute(statement)).all())

    async def _value_counts(
        self, found: CTE, column: ColumnElement[str | None], limit: int | None = None, listed: bool = False,
    ) -> tuple[MarketCountDTO, ...]:
        """Jobs per value, most common first; listed values are the "; "-joined items the page parser stores."""
        value = func.unnest(func.string_to_array(column, "; ")) if listed else column
        values = select(found.c.id, value.label("name"), found.c.workers).distinct().subquery()
        jobs = func.count().label("jobs")
        statement = (
            select(values.c.name, jobs, func.coalesce(func.sum(values.c.workers), 0).label("workers_needed"))
            .where(values.c.name.is_not(None), values.c.name != "")
            .group_by(values.c.name)
            .order_by(jobs.desc(), values.c.name)
            .limit(limit)
        )
        return tuple(MarketCountDTO.model_validate(row) for row in (await self._session.execute(statement)).all())

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
        # Rows that keep their category have fewer columns, so each kind is
        # sent as its own batch.
        for has_category in (True, False):
            rows = [
                {"id": job_id, **self._content(job), "last_seen_at": seen_at, "content_changed_at": seen_at}
                for job_id, job in jobs.items() if bool(job.category) == has_category
            ]
            if rows:
                await self._session.execute(update(Job), rows)

    async def mark_seen(self, job_ids: Collection[int], seen_at: datetime) -> None:
        if job_ids:
            await self._session.execute(
                update(Job).where(Job.id.in_(job_ids)).values(last_seen_at=seen_at)
            )

    async def list_category_evidence(self, feed_id: int) -> list[CategoryEvidenceDTO]:
        in_feed = select(JobFeedMembership.job_id).where(JobFeedMembership.feed_id == feed_id)
        confirmed = (
            select(JobFeedMembership.job_id, SourceFeed.id.label("feed_id"), SourceFeed.mapped_category)
            .join(SourceFeed)
            .where(SourceFeed.scope == "occupation", SourceFeed.mapping_status == "confirmed")
            .subquery()
        )
        statement = (
            select(Job.id, Job.category, Job.category_feed_id, confirmed.c.feed_id, confirmed.c.mapped_category)
            .outerjoin(confirmed, confirmed.c.job_id == Job.id)
            .where(Job.id.in_(in_feed), Job.category_source.is_distinct_from("description"))
            .order_by(Job.id, confirmed.c.feed_id)
        )
        evidence: dict[int, CategoryEvidenceDTO] = {}
        for job_id, category, category_feed_id, mapped_feed_id, mapped_category in await self._session.execute(statement):
            known = evidence.get(job_id) or CategoryEvidenceDTO(
                job_id=job_id, category=category, category_feed_id=category_feed_id, mappings=(),
            )
            if mapped_feed_id is not None:
                known = known.model_copy(update={"mappings": (*known.mappings, (mapped_feed_id, mapped_category))})
            evidence[job_id] = known
        return list(evidence.values())

    async def list_category_inputs(self) -> list[CategoryInputDTO]:
        # ARRAY(subquery) gives jobs without occupation feeds an empty array.
        feed_ids = func.array(
            select(JobFeedMembership.feed_id)
            .join(SourceFeed)
            .where(JobFeedMembership.job_id == Job.id, SourceFeed.scope == "occupation")
            .order_by(JobFeedMembership.feed_id)
            .scalar_subquery()
        )
        statement = (
            select(
                Job.source_job_id,
                case((Job.category_source == "description", Job.category)).label("description_category"),
                feed_ids.label("occupation_feed_ids"), Job.category, Job.category_source, Job.category_feed_id,
            )
            .where(listed_condition())
            .order_by(Job.id)
        )
        result = await self._session.execute(statement)
        return [CategoryInputDTO.model_validate(row) for row in result.all()]

    async def set_feed_categories(self, categories: Mapping[int, FilledCategoryDTO | None]) -> None:
        rows = [
            {"job_id": job_id, "new_category": filled.category if filled else None,
             "new_source": "feed" if filled else None, "new_feed_id": filled.feed_id if filled else None}
            for job_id, filled in categories.items()
        ]
        if rows:
            # A Core update, so the extra WHERE works for every row of the batch.
            jobs = Job.__table__
            await self._session.execute(
                update(jobs)
                .where(jobs.c.id == bindparam("job_id"), jobs.c.category_source.is_distinct_from("description"))
                .values(category=bindparam("new_category"), category_source=bindparam("new_source"),
                        category_feed_id=bindparam("new_feed_id")),
                rows,
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

    async def record_page(
        self, job_id: int, page: ParsedJobPageDTO, conditions: JobConditionsDTO, source_hash: str, checked_at: datetime,
    ) -> None:
        await self._session.execute(update(Job).where(Job.id == job_id).values(
            page_status="fetched", page_checked_at=checked_at, page_fetched_at=checked_at,
            page_source_hash=source_hash, page_error=None,
            **{f"page_{name}": value for name, value in page.model_dump().items()}, **self._conditions(conditions),
        ))

    async def record_page_problem(self, job_id: int, status: str, error: str, checked_at: datetime) -> None:
        if status not in {"unavailable", "failed"}:
            raise ValueError("A page problem is either 'unavailable' or 'failed'.")
        await self._session.execute(update(Job).where(Job.id == job_id).values(
            page_status=status, page_checked_at=checked_at, page_error=error,
        ))

    async def list_condition_inputs(self) -> list[JobConditionsInputDTO]:
        statement = (
            select(Job.id, *PAGE_CONDITIONS.values(), *STORED_CONDITIONS.values())
            .where(Job.page_fetched_at.is_not(None))
            .order_by(Job.id)
            .with_for_update()
        )
        result = await self._session.execute(statement)
        return [
            JobConditionsInputDTO(
                job_id=row[Job.id],
                raw=RawJobConditionsDTO(**{name: row[column] for name, column in PAGE_CONDITIONS.items()}),
                stored=JobConditionsDTO(**{name: row[column] for name, column in STORED_CONDITIONS.items()}),
            )
            for row in result.mappings()
        ]

    async def set_conditions(self, conditions: Mapping[int, JobConditionsDTO]) -> None:
        rows = [{"id": job_id, **self._conditions(values)} for job_id, values in conditions.items()]
        if rows:
            await self._session.execute(update(Job), rows)

    @staticmethod
    def _conditions(conditions: JobConditionsDTO) -> dict[str, object]:
        """Column values for normalised conditions, with tuples as lists for the array columns."""
        return {STORED_CONDITIONS[name].key: value for name, value in conditions.model_dump(mode="json").items()}

    @staticmethod
    def _content(job: ParsedJobDTO) -> dict[str, object]:
        """Column values for a parsed job; without a category, the stored one is kept."""
        content = job.model_dump(exclude={"category"}) | {"quality_flags": list(job.quality_flags)}
        if job.category:
            content |= {"category": job.category, "category_source": "description", "category_feed_id": None}
        return content


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


def terms_condition(terms: Sequence[str], weight: str = "") -> ColumnElement[bool]:
    """True when every term starts a word of the search document, or of its part with that weight."""
    query = " & ".join(f"{term}:*{weight}" for term in terms)
    return Job.search_vector.bool_op("@@")(func.to_tsquery("simple", query))


def filter_conditions(criteria: JobFilterCriteriaDTO) -> list[ColumnElement[bool]]:
    """Conditions for listed jobs matching every criterion, so search and statistics count the same jobs."""
    conditions = [listed_condition(criteria.county_id)]
    if criteria.terms:
        conditions.append(terms_condition(criteria.terms))
    if criteria.category is not None:
        conditions.append(func.upper(Job.category) == func.upper(criteria.category))
    if criteria.open_on is not None:
        conditions.append(open_condition(criteria.open_on))
    return conditions


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
