from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from FOIHireloom.db.models import Job
from FOIHireloom.domain.job_search import (
    INVALID_CURSOR, JobCursorCodec, condition_criteria, local_date, search_terms,
)
from FOIHireloom.db.uow.base import UnitOfWork, UnitOfWorkFactory
from FOIHireloom.dto.job_comparison import (
    MAX_COMPARED_JOBS,
    MIN_COMPARED_JOBS,
    ComparedJobDTO,
    JobComparisonConditionsDTO,
    JobComparisonDTO,
)
from FOIHireloom.dto.job_market import JobMarketCriteriaDTO, JobMarketFiltersDTO, JobMarketStatsDTO
from FOIHireloom.dto.job_skills import Skill
from FOIHireloom.dto.job_search import (
    CategoryDTO,
    CoverageDTO,
    JobCardsPageDTO,
    JobCountyDTO,
    JobCursorDTO,
    JobDetailsDTO,
    JobSearchCriteriaDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    JobSummaryDTO,
    RegionDTO,
    RegionFreshnessDTO,
    UnknownConditionsDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .croatian_counties import CroatianCountyCatalog
from .feed_coverage import FeedCoverage
from .job_comparison import JobComparator
from .job_presentation import JobPresenter

# Job IDs are bigint identities.
MAX_JOB_ID = 2**63 - 1

# JobResult makes a page entry from a job, today, its county, its title match and the skills searched for.
type JobResult[T: JobSummaryDTO] = Callable[[Job, date, JobCountyDTO | None, bool | None, tuple[Skill, ...]], T]


@dataclass(frozen=True)
class SearchPage[T: JobSummaryDTO]:
    """SearchPage holds one page of jobs with what search and search_cards both report about it.

    unknown counts the jobs left out only for unknown condition values.
    """

    jobs: tuple[T, ...]
    next_cursor: str | None
    coverage: CoverageDTO
    today: date
    unknown: UnknownConditionsDTO


class JobSearchService(JobSearchServiceInterface):
    """Missing from every feed does not mean closed: such jobs leave the
    default search but stay available through get_job().

    A county's data is stale once its feeds last succeeded more than
    the coverage policy allows. Every search page reports the freshness of the counties
    it covered, so a gap in the data is not mistaken for an absence of jobs.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        counties: CroatianCountyCatalog,
        feed_coverage: FeedCoverage,
        comparator: JobComparator,
        presenter: JobPresenter,
        cursors: JobCursorCodec,
    ) -> None:
        self._uow_factory = uow_factory
        self._counties = counties
        self._feed_coverage = feed_coverage
        self._comparator = comparator
        self._presenter = presenter
        self._cursors = cursors

    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        page = await self._search(filters, self._presenter.summary)
        return JobSearchPageDTO(jobs=page.jobs, next_cursor=page.next_cursor, coverage=page.coverage,
                                unknown_conditions=page.unknown.by_filter, unknown_total=page.unknown.total)

    async def search_cards(self, filters: JobSearchFiltersDTO) -> JobCardsPageDTO:
        page = await self._search(filters, self._presenter.card)
        return JobCardsPageDTO(jobs=page.jobs, next_cursor=page.next_cursor, coverage=page.coverage, today=page.today,
                               unknown_conditions=page.unknown.by_filter, unknown_total=page.unknown.total)

    async def _search[T: JobSummaryDTO](self, filters: JobSearchFiltersDTO, result: JobResult[T]) -> SearchPage[T]:
        """One page of jobs, each made by result."""
        terms = search_terms(filters.query)
        conditions = condition_criteria(filters)
        after = self._cursors.decode(filters.cursor) if filters.cursor else None
        if after is not None and not self._cursor_fits(after, terms, conditions["skills"]):
            raise InvalidJobSearchError(INVALID_CURSOR)
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            today = local_date(now)
            county_id, county_code = await self._resolve_county(work, filters.county)
            criteria = JobSearchCriteriaDTO(
                terms=terms,
                county_id=county_id,
                category=self._category(filters.category),
                open_on=None if filters.include_expired else today,
                **conditions,
                after=after,
                # One extra row tells whether another page exists.
                limit=filters.limit + 1,
            )
            found = await work.jobs.search(criteria)
            unknown = await work.jobs.count_unknown_conditions(criteria)
            counties = self._first_county(await work.job_feed_memberships.list_counties([hit.job.id for hit in found]))
            jobs = [result(hit.job, today, counties.get(hit.job.id), hit.title_match, criteria.skills or ())
                    for hit in found]
            regions = self._feed_coverage.freshness(await work.counties.list_feed_checks(), now)
        page = jobs[:filters.limit]
        return SearchPage(
            jobs=tuple(page), next_cursor=self._cursors.encode(page[-1]) if len(jobs) > filters.limit else None,
            coverage=self._county_coverage(regions, county_code), today=today, unknown=unknown,
        )

    @staticmethod
    def _cursor_fits(after: JobCursorDTO, terms: tuple[str, ...], skills: Sequence[str] | None) -> bool:
        """Whether the cursor carries exactly the ranks this search uses."""
        wanted_skills = skills or ()
        return ((after.title_match is None) == (not terms)
                and (after.skill_matches is None) == (not skills)
                and (after.skill_matches is None or after.skill_matches <= len(wanted_skills)))

    async def market_stats(self, filters: JobMarketFiltersDTO) -> JobMarketStatsDTO:
        terms = search_terms(filters.query)
        conditions = condition_criteria(filters)
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            today = local_date(now)
            county_id, county_code = await self._resolve_county(work, filters.county)
            criteria = JobMarketCriteriaDTO(
                terms=terms,
                county_id=county_id,
                category=self._category(filters.category),
                open_on=None if filters.include_expired else today,
                **conditions,
                today=today,
                top=filters.top,
            )
            aggregates = await work.jobs.market_aggregates(criteria)
            unknown = await work.jobs.count_unknown_conditions(criteria)
            regions = self._feed_coverage.freshness(await work.counties.list_feed_checks(), now)
        return JobMarketStatsDTO(**aggregates.model_dump(), today=today,
                                 coverage=self._county_coverage(regions, county_code),
                                 unknown_conditions=unknown.by_filter, unknown_total=unknown.total)

    async def get_job(self, job_id: int) -> JobDetailsDTO:
        async with self._uow_factory() as work:
            job = await work.jobs.get_by_id(job_id)
            if job is None:
                raise NotFoundError("job", str(job_id))
            now = await work.transaction_time()
            listings = await work.job_feed_memberships.list_listings(job_id)
            county = self._first_county(await work.job_feed_memberships.list_counties([job_id])).get(job_id)
            listings = [
                listing.model_copy(update={
                    "data_status": self._feed_coverage.status([listing.feed_last_success_at], now),
                })
                for listing in listings
            ]
            return self._presenter.details(job, local_date(now), county, listings)

    async def compare_jobs(
        self, job_ids: Sequence[int], conditions: JobComparisonConditionsDTO | None = None,
    ) -> JobComparisonDTO:
        ids = tuple(job_ids)
        if not MIN_COMPARED_JOBS <= len(ids) <= MAX_COMPARED_JOBS:
            raise InvalidJobSearchError(
                f"Choose {MIN_COMPARED_JOBS} or {MAX_COMPARED_JOBS} jobs to compare, not {len(ids)}.")
        if repeated := sorted({job_id for job_id in ids if ids.count(job_id) > 1}):
            raise InvalidJobSearchError(
                f"Choose different jobs to compare; given more than once: {', '.join(map(str, repeated))}.")
        if conditions is not None and not conditions.model_dump(exclude_none=True):
            conditions = None
        async with self._uow_factory() as work:
            today = local_date(await work.transaction_time())
            # An ID outside the identity column's range cannot name a job.
            found = await work.jobs.list_by_ids([job_id for job_id in ids if 1 <= job_id <= MAX_JOB_ID])
            jobs = {job.id: job for job in found}
            if missing := [str(job_id) for job_id in ids if job_id not in jobs]:
                raise NotFoundError("job" if len(missing) == 1 else "jobs", ", ".join(missing))
            counties = self._first_county(await work.job_feed_memberships.list_counties(ids))
            compared = [self._presenter.comparison_input(jobs[job_id], today, counties.get(job_id)) for job_id in ids]
        return JobComparisonDTO(
            today=today,
            jobs=tuple(
                ComparedJobDTO(**job.summary.model_dump(include=set(ComparedJobDTO.model_fields)),
                               conditions=job.conditions)
                for job in compared
            ),
            rows=self._comparator.rows(compared, today, conditions),
            conditions=conditions,
        )

    async def list_regions(self) -> tuple[RegionDTO, ...]:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            regions = await work.counties.list_regions(local_date(now))
            freshness = {region.code: region for region in self._feed_coverage.freshness(await work.counties.list_feed_checks(), now)}
        return tuple(
            region.model_copy(update={
                "data_status": freshness[region.code].data_status,
                "last_success_at": freshness[region.code].last_success_at,
            })
            for region in regions
        )

    async def list_categories(self) -> tuple[CategoryDTO, ...]:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            return tuple(await work.jobs.list_categories(local_date(now)))

    def _county_coverage(self, regions: Sequence[RegionFreshnessDTO], county_code: str | None) -> CoverageDTO:
        """The coverage of the searched county, or of every county when the search has none."""
        if county_code is not None:
            regions = [region for region in regions if region.code == county_code]
        return self._feed_coverage.coverage(regions)

    @staticmethod
    def _category(category: str | None) -> str | None:
        """A blank category is no filter."""
        return (category or "").strip() or None

    async def _resolve_county(self, work: UnitOfWork, county: str | None) -> tuple[int | None, str | None]:
        """ID and code of the requested county, or None for both without one; raise NotFoundError if unknown."""
        if not (county := (county or "").strip()):
            return None, None
        entity = await work.counties.get_by_code(self._county_code(county))
        if entity is None:
            raise NotFoundError("county", county)
        return entity.id, entity.code

    def _county_code(self, county: str) -> str:
        """Accept a county name as well as a code; 'Grad Zagreb' and 'grad-zagreb' are the same county."""
        definition = self._counties.match(county)
        return definition.code if definition is not None else county.casefold()

    @staticmethod
    def _first_county(counties: Sequence[JobCountyDTO]) -> dict[int, JobCountyDTO]:
        """Keep one county per job, preferring a feed that still lists it; HZZ lists a job in one county."""
        first: dict[int, JobCountyDTO] = {}
        for county in counties:
            first.setdefault(county.job_id, county)
        return first
