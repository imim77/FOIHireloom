from collections.abc import Awaitable
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from FOIHireloom.dto.job_conditions import Contract, EducationLevel, EmploymentTag
from FOIHireloom.dto.job_market import (
    DEFAULT_MARKET_TOP,
    MAX_MARKET_TOP,
    CountyMetric,
    JobMarketFiltersDTO,
    JobMarketStatsDTO,
    JobsByCountyDTO,
)
from FOIHireloom.dto.job_search import (
    MAX_EXPERIENCE_MONTHS,
    MAX_PAGE_SIZE,
    MAX_QUERY_LENGTH,
    CategoryDTO,
    JobCardsDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError, PersistenceError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .apps import job_cards, jobs_by_county
from .apps.views import JOB_CARDS, JOBS_BY_COUNTY
from .tool_provider import ToolGroup

# Key of the search service in the server's lifespan context.
JOB_SEARCH_SERVICE = "job_search_service"

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

CATEGORY_DESCRIPTION = (
    "Exact category name from list_categories; letter case is ignored. A job's category is stated in its "
    "description or filled in from an HZZ occupation feed verified on its jobs. Jobs without one do not match, "
    "so also use query when every job of an occupation matters."
)
# The condition filters, shared by the tools that choose jobs as search_jobs does.
MaxExperienceMonths = Annotated[int | None, Field(
    ge=0, le=MAX_EXPERIENCE_MONTHS,
    description="Most experience in months the job may ask for; 0 finds jobs that need none ('Nije važno') and "
                "trainee ads.",
)]
ContractFilter = Annotated[Contract | None, Field(
    description="'permanent' (na neodređeno), 'fixed_term' (na određeno) or 'other' (other forms of work).",
)]
FullTime = Annotated[bool | None, Field(
    description="true for full-time jobs, false for part-time ones (under 40 hours a week).",
)]
Education = Annotated[EducationLevel | None, Field(
    description="The user's education level; finds jobs that accept it: 'primary_lower' (lower primary grades), "
                "'primary' (primary school), 'secondary_3' (3-year secondary school), 'secondary_4' (4-year "
                "secondary school), 'college' (viša or bachelor's) or 'university' (faculty, master's or doctorate).",
)]
Accommodation = Annotated[bool | None, Field(
    description="true for jobs offering accommodation (shared, single or family), false for jobs offering none.",
)]
EmploymentTags = Annotated[tuple[EmploymentTag, ...] | None, Field(
    description="Tags the job must all have: 'new_position', 'vacancy', 'replacement', 'increased_workload', "
                "'seasonal', 'reappointment', 'trainee', 'retirees' (pensioners may apply) or 'disability' "
                "(people with disabilities may apply).",
)]
Place = Annotated[str | None, Field(
    max_length=MAX_QUERY_LENGTH,
    description="Place of work in the nominative, e.g. 'Rijeka', not 'Rijeci'. Its words must appear as whole "
                "words in the job page's place of work or the feed's municipality, ignoring case and diacritics, "
                "so 'Varazdin' finds 'VARAŽDIN', 'Pula' finds 'PULA-POLA' and 'Zagreb' finds 'ZAGREB-DUBRAVA'.",
)]


class JobTools(ToolGroup):
    """MCP tools over stored HZZ job advertisements.

    Tools only translate arguments and errors; JobSearchService holds the
    rules. The server's lifespan must provide the service under
    JOB_SEARCH_SERVICE.
    """

    def register(self, server: FastMCP) -> None:
        @server.tool(annotations=READ_ONLY)
        async def search_jobs(
            ctx: Context,
            query: Annotated[str | None, Field(
                max_length=MAX_QUERY_LENGTH,
                description="Words to find, e.g. 'kuhar', 'medicinska sestra', 'njemački' or 'Pula'. Searches "
                            "the title, the full description, the employer, the place of work and the required "
                            "education. Each word matches the start of a word, with or without Croatian "
                            "diacritics, and all words must match. Case endings and feminine -ica forms are "
                            "removed, so 'njemački' also finds 'njemačkog' and 'kuharica' finds 'KUHAR/ICA'. "
                            "Forms with sound changes are not, so write places in the base form ('Rijeka', not "
                            "'Rijeci') or use county.",
            )] = None,
            county: Annotated[str | None, Field(
                description="County code or name from list_regions, e.g. 'grad-zagreb' or 'Istarska županija'.",
            )] = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: Annotated[bool, Field(
                description="Also return jobs whose application deadline has passed.",
            )] = False,
            limit: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE, description="Jobs per page.")] = MAX_PAGE_SIZE,
            cursor: Annotated[str | None, Field(
                description="next_cursor from the previous page, with the same other arguments.",
            )] = None,
        ) -> JobSearchPageDTO:
            """Search Croatian Employment Service (HZZ) job advertisements, newest first.

            Returns jobs still listed in an HZZ county feed. With a query,
            jobs whose title contains every query word come first
            (title_match true), then jobs that match only elsewhere, such as
            a driving licence or a language mentioned in the description;
            each group is ordered newest first. deadline_on is
            the application deadline; with deadline_source 'job_page' it is
            the "Natječaj vrijedi do" date from the job's HZZ page. Jobs whose
            known deadline has passed are left out unless include_expired is
            true; jobs without a known deadline are included, with
            deadline_passed null. Null fields were not stated by the source;
            display_title labels jobs without a title. Show display_location
            as the job's location: it is the place of work from the job page
            when that has been read, otherwise the town from the feed or, when
            HZZ gave none, the county. Use get_job for the full details, and
            canonical_url to view or apply on the HZZ site.

            The condition filters (max_experience_months, contract,
            full_time, education, accommodation, employment_tags and place)
            use the values read from the job's HZZ page, and place also the
            feed's municipality. A job whose value is unknown, because its
            page was not read or does not state it, never matches.
            unknown_total is the number of jobs left out only for unknown
            values: they meet or might meet every condition filter.
            unknown_conditions gives, per condition filter, how many of them
            have an unknown value for it; a job can count under several.
            Whenever unknown_total is not 0, tell the user how many jobs might
            also match and which filters had unknown values, and never say
            those jobs meet the conditions.

            coverage says how current the searched counties are. When
            coverage.warning is set, tell the user that results may be
            outdated or incomplete; few or no results then do not mean HZZ
            has no such jobs.
            """
            filters = JobSearchFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired, limit=limit,
                cursor=cursor,
            )
            return await self._call(service(ctx).search(filters))

        @server.tool(app=AppConfig(resource_uri=JOB_CARDS.uri), annotations=READ_ONLY)
        async def show_jobs(
            ctx: Context,
            query: Annotated[str | None, Field(
                max_length=MAX_QUERY_LENGTH,
                description="Words chosen as for search_jobs, e.g. 'kuhar' or 'njemački'; leave out for the newest jobs.",
            )] = None,
            county: Annotated[str | None, Field(
                description="County code or name from list_regions, e.g. 'grad-zagreb' or 'Istarska županija'.",
            )] = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: Annotated[bool, Field(
                description="Also show jobs whose application deadline has passed.",
            )] = False,
            limit: Annotated[int, Field(
                ge=1, le=MAX_PAGE_SIZE,
                description="Cards to show; keep the default unless the user asks for a number.",
            )] = job_cards.DEFAULT_LIMIT,
            cursor: Annotated[str | None, Field(
                description="next_cursor from the previous result, with the same other arguments.",
            )] = None,
        ) -> JobCardsDTO:
            """Show the user the jobs search_jobs would find as cards, newest first.

            Use it when the user wants to see or browse jobs, not just read
            about them. Hosts that support MCP Apps draw a card per job: the
            employer, the title, the place, the employment type, working
            hours, education, experience, workers sought, accommodation and
            the application deadline, with a link to the HZZ advertisement.
            The user can load more cards there. Every host also gets the
            data: the jobs as in search_jobs plus those job page values, which
            are null until the job's HZZ page has been read. Condition
            filters, unknown_total and unknown_conditions work as in
            search_jobs; report unknown_total whenever it is not 0. When
            coverage.warning is set, tell the user the results may be
            outdated or incomplete.
            """
            filters = JobSearchFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired, limit=limit,
                cursor=cursor,
            )
            return job_cards.job_cards(await self._call(service(ctx).search_cards(filters)), filters)

        @server.tool(annotations=READ_ONLY)
        async def job_market_stats(
            ctx: Context,
            query: Annotated[str | None, Field(
                max_length=MAX_QUERY_LENGTH,
                description="Words chosen as for search_jobs, e.g. 'kuhar' or 'njemački'; leave out for all jobs.",
            )] = None,
            county: Annotated[str | None, Field(
                description="County code or name from list_regions, e.g. 'grad-zagreb' or 'Istarska županija'.",
            )] = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: Annotated[bool, Field(
                description="Also count jobs whose application deadline has passed.",
            )] = False,
            top: Annotated[int, Field(
                ge=1, le=MAX_MARKET_TOP, description="Entries in the employers list.",
            )] = DEFAULT_MARKET_TOP,
        ) -> JobMarketStatsDTO:
            """Count the jobs search_jobs would find for the same filters, broken down for labour market questions.

            Use it for questions such as where most jobs of a kind are, which
            employers hire most, or what share is permanent; use search_jobs
            to list the jobs themselves. jobs is the number of matching jobs
            and workers_needed the positions their HZZ pages state, so one job
            can seek several workers. Each breakdown entry gives jobs and
            workers_needed per value, most common first.

            counties cover every matching job. categories cover only the
            with_category jobs: category_from_description of them state it in
            their own description, category_from_feed got it from an HZZ
            occupation feed verified on its jobs. The rest have an unknown
            category, not a different one; tell the user the actual coverage
            (with_category of jobs) whenever you use categories.
            The other breakdowns come from the job pages, so they cover at
            most with_details jobs, and each counts only jobs whose value is
            known: employers; contracts ('permanent', 'fixed_term', 'other');
            employment_tags (codes as in the employment_tags argument);
            working_time ('full_time', 'part_time'); experience_bands ('none'
            for no experience or trainee ads, '1_to_12_months',
            '13_to_36_months', 'over_36_months'); education_levels (each
            level a job accepts, codes as in the education argument);
            accommodation ('none', 'shared', 'single', 'family');
            schedule_tags ('morning', 'afternoon', 'two_shifts',
            'three_shifts', 'split' for split shifts, 'night',
            'weekends_holidays'); transport_allowance ('full', 'partial',
            'none'). A job can have several employment tags, education
            levels and schedule tags, so those counts may add up to more than
            jobs. published_recently and closing_soon count jobs published in
            the last window_days days, or closing within the next window_days
            days, counted from today. Condition filters, unknown_total and
            unknown_conditions work as in search_jobs; report unknown_total
            whenever it is not 0, as jobs that might also match.

            coverage says how current the counted counties are. When
            coverage.warning is set, tell the user the numbers may be
            outdated or incomplete.
            """
            filters = JobMarketFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired, top=top,
            )
            return await self._call(service(ctx).market_stats(filters))

        @server.tool(app=AppConfig(resource_uri=JOBS_BY_COUNTY.uri), annotations=READ_ONLY)
        async def show_jobs_by_county(
            ctx: Context,
            query: Annotated[str | None, Field(
                max_length=MAX_QUERY_LENGTH,
                description="Words chosen as for search_jobs, e.g. 'kuhar' or 'njemački'; leave out for all jobs.",
            )] = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: Annotated[bool, Field(
                description="Also count jobs whose application deadline has passed.",
            )] = False,
            top: Annotated[int, Field(
                ge=1, le=jobs_by_county.MAX_TOP,
                description="Columns the chart shows before the user expands it to every county; keep the default "
                            "unless the user asks for a number.",
            )] = jobs_by_county.DEFAULT_TOP,
            metric: Annotated[CountyMetric, Field(
                description="What to rank and draw the counties by: 'jobs' (job ads) or 'workers_needed' (positions "
                            "the ads seek; one ad can seek several workers). Pick the one the question is about, "
                            "e.g. 'workers_needed' for which county needs the most workers.",
            )] = "jobs",
        ) -> JobsByCountyDTO:
            """Show the user a chart of the counties ranked by matching jobs or by workers sought.

            Use it when the user wants to see where jobs of a kind are, or
            which county needs the most workers, not just read it. Hosts that
            support MCP Apps draw the top counties as columns the user can
            hover and select, with a button that opens every county full
            screen. Every host also gets the data: each county with matching
            jobs, ranked by metric, with jobs, workers_needed and share
            (percent of total_jobs). Condition filters, unknown_total and
            unknown_conditions work as in search_jobs; report unknown_total
            whenever it is not 0. When coverage.warning is set, tell the user
            the numbers may be outdated or incomplete.
            """
            filters = JobMarketFiltersDTO(
                query=query, category=category, max_experience_months=max_experience_months, contract=contract,
                full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired,
            )
            stats = await self._call(service(ctx).market_stats(filters))
            return jobs_by_county.jobs_by_county(stats, top, query, category, metric)

        @server.tool(annotations=READ_ONLY)
        async def get_job(
            ctx: Context,
            job_id: Annotated[int, Field(ge=1, le=2**63 - 1, description="id of a job from search_jobs.")],
        ) -> JobDetailsDTO:
            """Return one stored job advertisement with its details and county listings.

            Once the job's HZZ page has been read (details_status 'fetched'),
            description_text is the full text and the employment type, working
            hours, accommodation, education and experience come from the page.
            Before that, description_text is the feed's summary, which HZZ
            cuts at 512 characters; quality_flags marks fields that may be
            incomplete. details_status 'unavailable' means HZZ showed an error
            page, not that the job closed. A listing with presence_status 'missing'
            means the job left that feed, not that it was filled or closed;
            availability_status stays 'unknown' without evidence either way.
            A listing is only as current as its feed: data_status 'stale' or
            'unavailable' means its presence_status may be out of date.
            """
            return await self._call(service(ctx).get_job(job_id))

        @server.tool(annotations=READ_ONLY)
        async def list_regions(ctx: Context) -> list[RegionDTO]:
            """List the Croatian counties with the number of jobs search_jobs finds in each by default.

            data_status is 'fresh' when the county's feeds were checked
            recently, 'stale' when the last successful check is too old, and
            'unavailable' when the county has no working feed.
            """
            return list(await self._call(service(ctx).list_regions()))

        @server.tool(annotations=READ_ONLY)
        async def list_categories(ctx: Context) -> list[CategoryDTO]:
            """List job categories with the number of jobs search_jobs finds in each by default, most common first.

            A job's category is stated in its description or filled in from an
            HZZ occupation feed verified on its jobs. Jobs without one are not
            counted, so the counts may not add up to all jobs; also search by
            query when every job of an occupation matters.
            """
            return list(await self._call(service(ctx).list_categories()))

    @staticmethod
    async def _call[T](operation: Awaitable[T]) -> T:
        """Turn errors the caller can act on into tool errors; database details stay in the server log."""
        try:
            return await operation
        except (NotFoundError, InvalidJobSearchError) as error:
            raise ToolError(error.details) from error
        except PersistenceError as error:
            raise ToolError("Job data is temporarily unavailable; try again later.") from error


def service(ctx: Context) -> JobSearchServiceInterface:
    return ctx.lifespan_context[JOB_SEARCH_SERVICE]
