import base64
from collections.abc import Callable
from datetime import date
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from FOIHireloom.db.models import Job
from FOIHireloom.db.models.job import SEARCH_FOLD_FROM, SEARCH_FOLD_TO
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.job_search import (
    SEARCH_TERM,
    CategoryDTO,
    JobCursorDTO,
    JobDetailsDTO,
    JobSearchCriteriaDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    JobSummaryDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .croatian_counties import CroatianCountyCatalog

# HZZ deadlines are Croatian calendar days and stay open until the end of the day.
LOCAL_TIME_ZONE = ZoneInfo("Europe/Zagreb")
# The same folding as the stored search vector.
SEARCH_FOLD = str.maketrans(SEARCH_FOLD_FROM, SEARCH_FOLD_TO)


class JobSearchService(JobSearchServiceInterface):
    """Missing from every feed does not mean closed: such jobs leave the
    default search but stay available through get_job().
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork], counties: CroatianCountyCatalog) -> None:
        self._uow_factory = uow_factory
        self._counties = counties

    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        terms = self._terms(filters.query)
        after = self._decode_cursor(filters.cursor) if filters.cursor else None
        async with self._uow_factory() as work:
            today = await self._today(work)
            county_id = None
            if county := (filters.county or "").strip():
                entity = await work.counties.get_by_code(self._county_code(county))
                if entity is None:
                    raise NotFoundError("county", county)
                county_id = entity.id
            criteria = JobSearchCriteriaDTO(
                terms=terms,
                county_id=county_id,
                category=(filters.category or "").strip() or None,
                open_on=None if filters.include_expired else today,
                after=after,
                # One extra row tells whether another page exists.
                limit=filters.limit + 1,
            )
            jobs = [self._summary(job, today) for job in await work.jobs.search(criteria)]
        page = jobs[:filters.limit]
        next_cursor = self._encode_cursor(page[-1]) if len(jobs) > filters.limit else None
        return JobSearchPageDTO(jobs=tuple(page), next_cursor=next_cursor)

    async def get_job(self, job_id: int) -> JobDetailsDTO:
        async with self._uow_factory() as work:
            job = await work.jobs.get_by_id(job_id)
            if job is None:
                raise NotFoundError("job", str(job_id))
            today = await self._today(work)
            listings = await work.job_feed_memberships.list_listings(job_id)
            return JobDetailsDTO.model_validate(job).model_copy(update={
                "deadline_passed": self._deadline_passed(job, today),
                "listings": tuple(listings),
            })

    async def list_regions(self) -> tuple[RegionDTO, ...]:
        async with self._uow_factory() as work:
            return tuple(await work.counties.list_regions(await self._today(work)))

    async def list_categories(self) -> tuple[CategoryDTO, ...]:
        async with self._uow_factory() as work:
            return tuple(await work.jobs.list_categories(await self._today(work)))

    @staticmethod
    async def _today(work: UnitOfWork) -> date:
        return (await work.transaction_time()).astimezone(LOCAL_TIME_ZONE).date()

    @staticmethod
    def _terms(query: str | None) -> tuple[str, ...]:
        if query is None or not query.strip():
            return ()
        terms = tuple(dict.fromkeys(SEARCH_TERM.findall(query.translate(SEARCH_FOLD).casefold())))
        if not terms:
            raise InvalidJobSearchError("The query contains no searchable words.")
        return terms

    def _county_code(self, county: str) -> str:
        """Accept a county name as well as a code; 'Grad Zagreb' and 'grad-zagreb' are the same county."""
        definition = self._counties.match(county)
        return definition.code if definition is not None else county.casefold()

    @staticmethod
    def _deadline_passed(job: Job, today: date) -> bool | None:
        return None if job.deadline_on is None else job.deadline_on < today

    def _summary(self, job: Job, today: date) -> JobSummaryDTO:
        return JobSummaryDTO.model_validate(job).model_copy(
            update={"deadline_passed": self._deadline_passed(job, today)}
        )

    @staticmethod
    def _encode_cursor(job: JobSummaryDTO) -> str:
        cursor = JobCursorDTO(published_on=job.published_on, id=job.id)
        return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> JobCursorDTO:
        try:
            return JobCursorDTO.model_validate_json(base64.urlsafe_b64decode(cursor.encode("ascii")))
        except (ValueError, ValidationError) as error:
            raise InvalidJobSearchError("The cursor is not valid; start the search again without it.") from error
