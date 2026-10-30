import base64
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from FOIHireloom.db.models import Job
from FOIHireloom.db.models.job import SEARCH_FOLD_FROM, SEARCH_FOLD_TO
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.job_search import (
    SEARCH_TERM,
    CategoryDTO,
    CountyFeedCheckDTO,
    CoverageDTO,
    DataStatus,
    JobCountyDTO,
    JobCursorDTO,
    JobDetailsDTO,
    JobSearchCriteriaDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    JobSummaryDTO,
    RegionDTO,
    RegionFreshnessDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .croatian_counties import CroatianCountyCatalog
from .croatian_stem import stem

# HZZ deadlines are Croatian calendar days and stay open until the end of the day.
LOCAL_TIME_ZONE = ZoneInfo("Europe/Zagreb")
# The same folding as the stored search vector.
SEARCH_FOLD = str.maketrans(SEARCH_FOLD_FROM, SEARCH_FOLD_TO)
# Counties named in a coverage warning before the rest are only counted.
WARNING_REGION_LIMIT = 5
INVALID_CURSOR = "The cursor is not valid; start the search again without it."


class JobSearchService(JobSearchServiceInterface):
    """Missing from every feed does not mean closed: such jobs leave the
    default search but stay available through get_job().

    A county's data is stale once its feeds last succeeded more than
    stale_after ago. Every search page reports the freshness of the counties
    it covered, so a gap in the data is not mistaken for an absence of jobs.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        counties: CroatianCountyCatalog,
        stale_after: timedelta = timedelta(hours=6),
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive.")
        self._uow_factory = uow_factory
        self._counties = counties
        self._stale_after = stale_after

    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        terms = self._terms(filters.query)
        after = self._decode_cursor(filters.cursor) if filters.cursor else None
        # A cursor orders by title match exactly when the search has a query.
        if after is not None and (after.title_match is None) != (not terms):
            raise InvalidJobSearchError(INVALID_CURSOR)
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            today = self._local_date(now)
            county_id = county_code = None
            if county := (filters.county or "").strip():
                entity = await work.counties.get_by_code(self._county_code(county))
                if entity is None:
                    raise NotFoundError("county", county)
                county_id, county_code = entity.id, entity.code
            criteria = JobSearchCriteriaDTO(
                terms=terms,
                county_id=county_id,
                category=(filters.category or "").strip() or None,
                open_on=None if filters.include_expired else today,
                after=after,
                # One extra row tells whether another page exists.
                limit=filters.limit + 1,
            )
            found = await work.jobs.search(criteria)
            counties = self._first_county(await work.job_feed_memberships.list_counties([hit.job.id for hit in found]))
            jobs = [self._summary(hit.job, today, counties.get(hit.job.id), hit.title_match) for hit in found]
            regions = self._freshness(await work.counties.list_feed_checks(), now)
        if county_code is not None:
            regions = [region for region in regions if region.code == county_code]
        page = jobs[:filters.limit]
        next_cursor = self._encode_cursor(page[-1]) if len(jobs) > filters.limit else None
        return JobSearchPageDTO(jobs=tuple(page), next_cursor=next_cursor, coverage=self._coverage(regions))

    async def get_job(self, job_id: int) -> JobDetailsDTO:
        async with self._uow_factory() as work:
            job = await work.jobs.get_by_id(job_id)
            if job is None:
                raise NotFoundError("job", str(job_id))
            now = await work.transaction_time()
            listings = await work.job_feed_memberships.list_listings(job_id)
            county = self._first_county(await work.job_feed_memberships.list_counties([job_id])).get(job_id)
            return JobDetailsDTO.model_validate(job).model_copy(update={
                **self._county_fields(county),
                **self._page_fields(job, self._local_date(now)),
                "description_text": job.page_description_text or job.description_text,
                "description_source": "job_page" if job.page_description_text else "feed" if job.description_text else None,
                "valid_from": job.page_valid_from,
                "workers_needed": job.page_workers_needed,
                "employment_type": job.page_employment_type,
                "working_hours": job.page_working_hours,
                "work_schedule": job.page_work_schedule,
                "accommodation": job.page_accommodation,
                "transport_allowance": job.page_transport_allowance,
                "education": job.page_education,
                "experience": job.page_experience,
                "details_checked_at": job.page_checked_at,
                "listings": tuple(
                    listing.model_copy(update={"data_status": self._status([listing.feed_last_success_at], now)})
                    for listing in listings
                ),
            })

    async def list_regions(self) -> tuple[RegionDTO, ...]:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            regions = await work.counties.list_regions(self._local_date(now))
            freshness = {region.code: region for region in self._freshness(await work.counties.list_feed_checks(), now)}
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
            return tuple(await work.jobs.list_categories(self._local_date(now)))

    @staticmethod
    def _local_date(moment: datetime) -> date:
        return moment.astimezone(LOCAL_TIME_ZONE).date()

    def _status(self, successes: Sequence[datetime | None], now: datetime) -> DataStatus:
        if not successes or None in successes:
            return "unavailable"
        return "stale" if min(successes) < now - self._stale_after else "fresh"

    def _freshness(self, checks: Sequence[CountyFeedCheckDTO], now: datetime) -> list[RegionFreshnessDTO]:
        counties: dict[str, tuple[str, list[datetime | None]]] = {}
        for check in checks:
            _, successes = counties.setdefault(check.code, (check.name, []))
            if check.feed_id is not None:
                successes.append(check.last_success_at)
        return [
            RegionFreshnessDTO(
                code=code, name=name, data_status=self._status(successes, now),
                last_success_at=min((moment for moment in successes if moment is not None), default=None),
            )
            for code, (name, successes) in counties.items()
        ]

    def _coverage(self, regions: Sequence[RegionFreshnessDTO]) -> CoverageDTO:
        affected = tuple(region for region in regions if region.data_status != "fresh")
        statuses = {region.data_status for region in affected}
        successes = [region.last_success_at for region in regions if region.last_success_at is not None]
        return CoverageDTO(
            data_status="unavailable" if "unavailable" in statuses or not regions else "stale" if affected else "fresh",
            data_as_of=min(successes, default=None),
            stale_after_hours=self._stale_after.total_seconds() / 3600,
            affected_regions=affected,
            warning=self._warning(affected, len(regions)),
        )

    def _warning(self, affected: Sequence[RegionFreshnessDTO], total: int) -> str | None:
        if total == 0:
            return "No counties are registered, so there is no job data to search."
        if not affected:
            return None
        named = ", ".join(self._describe(region) for region in affected[:WARNING_REGION_LIMIT])
        if len(affected) > WARNING_REGION_LIMIT:
            named += f" and {len(affected) - WARNING_REGION_LIMIT} more"
        scope = "the requested county" if total == 1 else f"{len(affected)} of {total} counties"
        hours = f"{self._stale_after.total_seconds() / 3600:g}"
        return (f"Job data for {scope} was not updated in the last {hours} hours or is unavailable: {named}. "
                "Results there may be outdated or incomplete; a job missing from them may still be advertised by HZZ.")

    @staticmethod
    def _describe(region: RegionFreshnessDTO) -> str:
        if region.last_success_at is None:
            return f"{region.name} (never loaded)"
        updated = f"last updated {region.last_success_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC"
        if region.data_status == "unavailable":
            updated += ", a feed never loaded"
        return f"{region.name} ({updated})"

    @staticmethod
    def _terms(query: str | None) -> tuple[str, ...]:
        if query is None or not query.strip():
            return ()
        # Stemmed, so "medicinske sestre" also finds "MEDICINSKA SESTRA".
        words = SEARCH_TERM.findall(query.translate(SEARCH_FOLD).casefold())
        terms = tuple(dict.fromkeys(stem(word) for word in words))
        if not terms:
            raise InvalidJobSearchError("The query contains no searchable words.")
        return terms

    def _county_code(self, county: str) -> str:
        """Accept a county name as well as a code; 'Grad Zagreb' and 'grad-zagreb' are the same county."""
        definition = self._counties.match(county)
        return definition.code if definition is not None else county.casefold()

    def _summary(self, job: Job, today: date, county: JobCountyDTO | None, title_match: bool | None) -> JobSummaryDTO:
        return JobSummaryDTO.model_validate(job).model_copy(
            update={**self._page_fields(job, today), **self._county_fields(county), "title_match": title_match}
        )

    @staticmethod
    def _page_fields(job: Job, today: date) -> dict[str, object]:
        """Values the job page refines once read; page columns stay None until then.

        Quality flags for a weakness the page made up for are dropped.
        """
        deadline = job.page_valid_until or job.deadline_on
        resolved = {
            "title_missing": bool(job.page_title), "title_truncated": bool(job.page_title),
            "description_truncated": bool(job.page_description_text), "deadline_unknown": deadline is not None,
        }
        return {
            "title": job.page_title or job.title,
            "deadline_on": deadline,
            "deadline_source": "job_page" if job.page_valid_until else "feed" if job.deadline_on else None,
            "deadline_passed": None if deadline is None else deadline < today,
            "work_place": job.page_work_place,
            "employer_name": job.page_employer_name,
            "quality_flags": tuple(flag for flag in job.quality_flags if not resolved.get(flag)),
            "details_status": job.page_status,
        }

    @staticmethod
    def _first_county(counties: Sequence[JobCountyDTO]) -> dict[int, JobCountyDTO]:
        """Keep one county per job, preferring a feed that still lists it; HZZ lists a job in one county."""
        first: dict[int, JobCountyDTO] = {}
        for county in counties:
            first.setdefault(county.job_id, county)
        return first

    @staticmethod
    def _county_fields(county: JobCountyDTO | None) -> dict[str, str | None]:
        if county is None:
            return {"county_code": None, "county_name": None}
        return {"county_code": county.county_code, "county_name": county.county_name}

    @staticmethod
    def _encode_cursor(job: JobSummaryDTO) -> str:
        cursor = JobCursorDTO(title_match=job.title_match, published_on=job.published_on, id=job.id)
        return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> JobCursorDTO:
        try:
            return JobCursorDTO.model_validate_json(base64.urlsafe_b64decode(cursor.encode("ascii")))
        except (ValueError, ValidationError) as error:
            raise InvalidJobSearchError(INVALID_CURSOR) from error
