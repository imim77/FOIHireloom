from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import CTE, ColumnElement, Date, Integer, bindparam, case, func, not_, or_, select, update

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.models.job import SEARCH_TITLE_WEIGHT
from FOIHireloom.dto.category_snapshot import CategoryInputDTO
from FOIHireloom.dto.forecast import WeeklyJobAdsRowDTO
from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_conditions import JobConditionsDTO, JobConditionsInputDTO, RawJobConditionsDTO
from FOIHireloom.dto.job_market import (
    MARKET_WINDOW_DAYS,
    CountyJobCountsRowDTO,
    CountyJobCriteriaDTO,
    CountyMarketCountDTO,
    JobMarketAggregatesDTO,
    JobMarketCriteriaDTO,
    MarketCountDTO,
)
from FOIHireloom.dto.job_page import JobPageTargetDTO
from FOIHireloom.dto.job_search import (
    CategoryDTO,
    JobFilterCriteriaDTO,
    JobSearchCriteriaDTO,
    UnknownConditionsDTO,
)
from FOIHireloom.dto.job_sync import CategoryEvidenceDTO, FilledCategoryDTO, JobSnapshotDTO
from FOIHireloom.dao.interfaces.job import JobRepository, JobSearchHit

from .job_predicates import (
    CONDITION_FILTERS, after_descending, condition_filters, county_placements, effective_deadline,
    filter_conditions, listed_condition, open_condition, page_due_condition, terms_condition,
)
from .sqla_base import SqlAlchemyRepository

# Columns by JobConditionsDTO field, and the page columns by RawJobConditionsDTO field.
STORED_CONDITIONS = {
    name: getattr(Job, "conditions_unrecognised" if name == "unrecognised" else name)
    for name in JobConditionsDTO.model_fields
}
PAGE_CONDITIONS = {name: getattr(Job, f"page_{name}") for name in RawJobConditionsDTO.model_fields}
# When a job's value for each JobConditionFiltersDTO filter is unknown.
UNKNOWN_CONDITIONS = {name: condition.unknown for name, condition in CONDITION_FILTERS.items()}
LISTED_MEMBERSHIP = JobFeedMembership.presence_status == "present"


class SqlAlchemyJobRepository(SqlAlchemyRepository, JobRepository):
    async def get_by_id(self, job_id: int) -> Job | None:
        return await self._session.get(Job, job_id)

    async def list_by_ids(self, job_ids: Collection[int]) -> list[Job]:
        if not job_ids:
            return []
        return list(await self._session.scalars(select(Job).where(Job.id.in_(job_ids))))

    async def search(self, criteria: JobSearchCriteriaDTO) -> list[JobSearchHit]:
        title_match = terms_condition(criteria.terms, SEARCH_TITLE_WEIGHT) if criteria.terms else None
        keys = self._search_keys(criteria, title_match)
        statement = select(Job, title_match).where(*filter_conditions(criteria))
        if criteria.after is not None:
            statement = statement.where(after_descending(keys))
        statement = statement.order_by(*(column.desc().nulls_last() for column, _ in keys)).limit(criteria.limit)
        return [JobSearchHit(job, matched) for job, matched in await self._session.execute(statement)]

    @staticmethod
    def _search_keys(
        criteria: JobSearchCriteriaDTO, title_match: ColumnElement[bool] | None,
    ) -> list[tuple[ColumnElement, object]]:
        """The descending sort keys of search, each paired with the cursor's value at that key."""
        def after(field: str) -> object:
            value = getattr(criteria.after, field) if criteria.after is not None else None
            return int(value) if isinstance(value, bool) else value  # title_match sorts as an integer.

        keys: list[tuple[ColumnElement, object]] = []
        if title_match is not None:
            keys.append((title_match.cast(Integer), after("title_match")))
        if criteria.skills:
            skill_matches = sum(
                case((Job.skills.contains([skill]), 1), else_=0) for skill in dict.fromkeys(criteria.skills)
            )
            keys.append((skill_matches, after("skill_matches")))
        keys.extend(((Job.published_on, after("published_on")), (Job.id, after("id"))))
        return keys

    async def count_unknown_conditions(self, criteria: JobFilterCriteriaDTO) -> UnknownConditionsDTO:
        conditions = condition_filters(criteria)
        if not conditions:
            return UnknownConditionsDTO()
        # A job could match a filter when it matches it or its value is unknown.
        possible = {name: or_(condition, UNKNOWN_CONDITIONS[name]) for name, condition in conditions.items()}
        counts = [
            func.count().filter(UNKNOWN_CONDITIONS[name], *(other for key, other in possible.items() if key != name))
            for name in conditions
        ]
        total = func.count().filter(*possible.values(), or_(*(UNKNOWN_CONDITIONS[name] for name in conditions)))
        # Every criterion but the condition filters, as search applies it.
        others = filter_conditions(criteria.model_copy(update=dict.fromkeys(conditions)))
        *by_filter, total = (await self._session.execute(select(*counts, total).select_from(Job).where(*others))).one()
        return UnknownConditionsDTO(by_filter=dict(zip(conditions, by_filter)), total=total)

    async def market_aggregates(self, criteria: JobMarketCriteriaDTO) -> JobMarketAggregatesDTO:
        found = (
            select(
                Job.id, Job.category, Job.category_source, Job.published_on, effective_deadline().label("deadline"),
                Job.page_fetched_at, Job.page_workers_needed.label("workers"), Job.page_employer_name, Job.contract,
                Job.employment_tags, Job.full_time, Job.experience_months, Job.education_levels, Job.accommodation,
                Job.schedule_tags, Job.transport_allowance,
            )
            .where(*filter_conditions(criteria))
            .cte("found")
        )
        return JobMarketAggregatesDTO(
            **await self._market_totals(found, criteria.today),
            unlisted_jobs=await self._session.scalar(
                select(func.count()).select_from(Job).where(not_(listed_condition()))
            ),
            counties=await self._county_counts(found),
            **await self._market_breakdowns(found, criteria.top),
        )

    async def _market_totals(self, found: CTE, today: date) -> dict[str, int]:
        totals = {
            "jobs": func.count(),
            "with_details": func.count().filter(found.c.page_fetched_at.is_not(None)),
            "category_from_description": func.count().filter(found.c.category_source == "description"),
            "category_from_feed": func.count().filter(found.c.category_source == "feed"),
            "workers_needed": self._workers_needed(found.c.workers),
            "published_recently": func.count().filter(
                found.c.published_on > today - timedelta(days=MARKET_WINDOW_DAYS)
            ),
            "closing_soon": func.count().filter(self._closes_soon(found.c.deadline, today)),
        }
        counted = dict(zip(totals, (await self._session.execute(select(*totals.values()))).one()))
        return counted | {"with_category": counted["category_from_description"] + counted["category_from_feed"]}

    async def _market_breakdowns(self, found: CTE, top: int) -> dict[str, tuple[MarketCountDTO, ...]]:
        """Counts per value for each breakdown field of JobMarketAggregatesDTO."""
        # Without an else, an unknown value stays NULL and is left out.
        working_time = case((found.c.full_time, "full_time"), (not_(found.c.full_time), "part_time"))
        experience_band = case(
            (found.c.experience_months == 0, "none"),
            (found.c.experience_months <= 12, "1_to_12_months"),
            (found.c.experience_months <= 36, "13_to_36_months"),
            (found.c.experience_months > 36, "over_36_months"),
        )
        values = {
            "categories": found.c.category,
            "employers": found.c.page_employer_name,
            "contracts": found.c.contract,
            "employment_tags": func.unnest(found.c.employment_tags),
            "working_time": working_time,
            "experience_bands": experience_band,
            "education_levels": func.unnest(found.c.education_levels),
            "accommodation": found.c.accommodation,
            "schedule_tags": func.unnest(found.c.schedule_tags),
            "transport_allowance": found.c.transport_allowance,
        }
        limits = {"employers": top}  # The other breakdowns have few values.
        return {name: await self._value_counts(found, value, limits.get(name)) for name, value in values.items()}

    async def _county_counts(self, found: CTE) -> tuple[CountyMarketCountDTO, ...]:
        placed = county_placements(LISTED_MEMBERSHIP, JobFeedMembership.job_id.in_(select(found.c.id)))
        jobs = func.count().label("jobs")
        statement = (
            select(County.code, County.name, jobs, self._workers_needed(found.c.workers).label("workers_needed"))
            .select_from(placed)
            .join(County, County.id == placed.c.county_id)
            .join(found, found.c.id == placed.c.job_id)
            .group_by(County.id)
            .order_by(jobs.desc(), County.name)
        )
        return tuple(await self._rows(statement, CountyMarketCountDTO))

    async def _value_counts(
        self, found: CTE, value: ColumnElement[str | None], limit: int | None = None,
    ) -> tuple[MarketCountDTO, ...]:
        """Jobs per value, most common first; with unnest() of an array a job counts once per item."""
        values = select(found.c.id, value.label("name"), found.c.workers).distinct().subquery()
        jobs = func.count().label("jobs")
        statement = (
            select(values.c.name, jobs, self._workers_needed(values.c.workers).label("workers_needed"))
            .where(values.c.name.is_not(None), values.c.name != "")
            .group_by(values.c.name)
            .order_by(jobs.desc(), values.c.name)
            .limit(limit)
        )
        return tuple(await self._rows(statement, MarketCountDTO))

    async def county_job_counts(self, criteria: CountyJobCriteriaDTO) -> list[CountyJobCountsRowDTO]:
        found = (
            select(Job.id, Job.page_workers_needed.label("workers"), Job.contract,
                   effective_deadline().label("deadline"))
            .where(*filter_conditions(criteria))
            .cte("found")
        )
        placed = county_placements(
            LISTED_MEMBERSHIP, SourceFeed.county_id.in_(criteria.county_ids),
            JobFeedMembership.job_id.in_(select(found.c.id)),
        )
        statement = (
            select(
                placed.c.county_id,
                func.count().label("jobs"),
                func.count(found.c.workers).label("with_workers_needed"),
                self._workers_needed(found.c.workers).label("workers_needed"),
                func.count(found.c.contract).label("with_contract"),
                func.count().filter(found.c.contract == "permanent").label("permanent"),
                func.count().filter(self._closes_soon(found.c.deadline, criteria.today)).label("closing_soon"),
            )
            .select_from(placed)
            .join(found, found.c.id == placed.c.job_id)
            .group_by(placed.c.county_id)
        )
        return await self._rows(statement, CountyJobCountsRowDTO)

    @staticmethod
    def _workers_needed(workers: ColumnElement[int | None]) -> ColumnElement[int]:
        """The workers the jobs ask for in all; a job that does not say adds none."""
        return func.coalesce(func.sum(workers), 0)

    @staticmethod
    def _closes_soon(deadline: ColumnElement[date | None], today: date) -> ColumnElement[bool]:
        return deadline.between(today, today + timedelta(days=MARKET_WINDOW_DAYS - 1))

    async def weekly_published_counts(
        self, county_ids: Collection[int], first_week: date, last_week: date,
    ) -> list[WeeklyJobAdsRowDTO]:
        if not county_ids:
            return []
        # Expired ads count too: a forecast of demand needs every ad published.
        placed = county_placements(SourceFeed.county_id.in_(county_ids))
        week = func.date_trunc("week", Job.published_on).cast(Date).label("week")  # ISO weeks start on Monday.
        statement = (
            select(placed.c.county_id, week, func.count().label("jobs"))
            .select_from(placed)
            .join(Job, Job.id == placed.c.job_id)
            .where(Job.published_on.between(first_week, last_week + timedelta(days=6)))
            .group_by(placed.c.county_id, week)
        )
        return await self._rows(statement, WeeklyJobAdsRowDTO)

    async def tracking_started_at(self) -> datetime | None:
        return await self._session.scalar(select(func.min(Job.first_seen_at)))

    async def list_categories(self, open_on: date) -> list[CategoryDTO]:
        open_jobs = func.count().label("open_jobs")
        statement = (
            select(Job.category.label("name"), open_jobs)
            .where(Job.category.is_not(None), listed_condition(), open_condition(open_on))
            .group_by(Job.category)
            .order_by(open_jobs.desc(), Job.category)
        )
        return await self._rows(statement, CategoryDTO)

    async def list_snapshots(self, source_job_ids: Collection[str]) -> list[JobSnapshotDTO]:
        if not source_job_ids:
            return []
        statement = select(Job.id, Job.source_job_id, Job.content_hash).where(
            Job.source_job_id.in_(source_job_ids)
        )
        return await self._rows(statement, JobSnapshotDTO)

    async def create_many(self, jobs: Sequence[ParsedJobDTO], seen_at: datetime) -> dict[str, int]:
        entities = [
            Job(**self._content(job), first_seen_at=seen_at, last_seen_at=seen_at,
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
        return await self._rows(statement, CategoryInputDTO)

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
        return await self._rows(statement, JobPageTargetDTO)

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
