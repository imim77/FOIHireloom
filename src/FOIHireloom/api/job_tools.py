from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from FOIHireloom.dto.job_search import (
    MAX_PAGE_SIZE,
    CategoryDTO,
    JobCardsDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .apps import job_cards
from .apps.views import JOB_CARDS
from .job_filters import (
    Accommodation, Category, ContractFilter, County, Education, EmploymentTags,
    FullTime, MaxExperienceMonths, Place, SearchQuery, Skills,
)
from .tool_provider import DATA_ONLY, ServiceToolGroup, tool_arguments

JOB_SEARCH_SERVICE = "job_search_service"

JobId = Annotated[int, Field(ge=1, le=2**63 - 1)]


class JobToolGroup(ServiceToolGroup[JobSearchServiceInterface]):
    """JobToolGroup is a group of MCP tools over stored HZZ job advertisements.

    The server's lifespan must provide JobSearchService under
    JOB_SEARCH_SERVICE. Raw search and comparison endpoints remain app-only;
    user requests go to the corresponding show_ workflows by default.
    """

    _service_key = JOB_SEARCH_SERVICE
    _caller_errors = (NotFoundError, InvalidJobSearchError)
    _unavailable_message = "Job data is temporarily unavailable; try again later."


class JobSearchTools(JobToolGroup):
    """JobSearchTools lists matching job ads, as raw pages for apps and as cards for the user."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.search_jobs, app=DATA_ONLY)
        self._add_tool(server, self.show_jobs, app=JOB_CARDS.app_config)

    async def search_jobs(
        self,
        ctx: Context,
        query: SearchQuery = None,
        county: County = None,
        category: Category = None,
        max_experience_months: MaxExperienceMonths = None,
        contract: ContractFilter = None,
        full_time: FullTime = None,
        education: Education = None,
        accommodation: Accommodation = None,
        employment_tags: EmploymentTags = None,
        place: Place = None,
        skills: Skills = None,
        include_expired: Annotated[bool, Field(
            description="Also return jobs whose application deadline has passed.",
        )] = False,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE, description="Jobs per page.")] = MAX_PAGE_SIZE,
        cursor: Annotated[str | None, Field(
            description="next_cursor from the previous page, with the same other arguments.",
        )] = None,
    ) -> JobSearchPageDTO:
        """App-only data search and pagination endpoint. For user job-search requests use show_jobs.

        show_jobs searches the same stored HZZ advertisements, returns job data
        and presents the results automatically. Prefer it even for "find jobs",
        "tražim posao" or "ima li poslova", without asking for a display format.
        This endpoint returns a page of summaries and next_cursor for app workflows.
        Keep the same filters when continuing a cursor. Missing fields are unknown;
        report unknown_total and coverage.warning. Use get_job for one job's full text.
        """
        filters = JobSearchFiltersDTO(**tool_arguments(locals()))
        return await self._call(self._service(ctx).search(filters))

    async def show_jobs(
        self,
        ctx: Context,
        query: SearchQuery = None,
        county: County = None,
        category: Category = None,
        max_experience_months: MaxExperienceMonths = None,
        contract: ContractFilter = None,
        full_time: FullTime = None,
        education: Education = None,
        accommodation: Accommodation = None,
        employment_tags: EmploymentTags = None,
        place: Place = None,
        skills: Skills = None,
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
        """Find job vacancies matching the user's occupation, location and working conditions.

        DEFAULT for finding or browsing individual jobs, including "Nađi mi posao",
        "Tražim posao kuhara u Istri", "Ima li poslova bez iskustva?" and
        "Find nursing jobs in Zagreb". Call directly; the user does not need to
        request cards, a visual display or a tool. Do not ask which format to use.
        Searches stored HZZ ads and automatically presents matching jobs as cards
        on supported hosts; the same call also returns structured job data.

        Extract only stated conditions into filters. "Posao kuhara sa smještajem"
        means query='kuhar', accommodation=true. Use place for a town and county
        for a county. Omit unspecified filters; exclude expired jobs by default.
        Put programming languages and tools in skills, not query. Title matches
        rank first, then the number of requested skills mentioned, then newest
        publication. When direct skill matches are few, also offer a separate
        search without skills for a related occupation or category, keeping the
        user's other filters. Label those as related jobs. Use next_cursor with
        unchanged filters for more results, get_job for one ad's full details,
        and canonical_url to read the original or apply.

        For counts or shares by accommodation use show_accommodation_comparison;
        for where jobs or workers are concentrated use show_jobs_by_county.
        Compare only jobs the user selected with show_job_comparison.
        Null conditions mean unknown, never "not required". Report unknown_total,
        unknown_note and coverage_note when present; stale or empty results do
        not prove there are no jobs.
        """
        filters = JobSearchFiltersDTO(**tool_arguments(locals()))
        return job_cards.job_cards(await self._call(self._service(ctx).search_cards(filters)), filters)


class JobDetailTools(JobToolGroup):
    """JobDetailTools reads one job ad the user already found."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.get_job)

    async def get_job(
        self,
        ctx: Context,
        job_id: Annotated[JobId, Field(description="id of a job from earlier show_jobs results.")],
    ) -> JobDetailsDTO:
        """Read the full details of one job the user already found or selected.

        Use for "Reci mi više o ovom oglasu", "Koji je rok prijave?" or a
        specific ad's requirements, taking job_id from earlier show_jobs results.
        For a new job search use show_jobs; for comparing 2 or 3 selected ads
        use show_job_comparison. Do not invent an ID.

        Returns stored feed/page text, conditions, deadline, original HZZ URL and
        feed listings. Page text replaces the truncated feed summary once fetched.
        Null fields are unknown. An unavailable page or a missing feed listing
        does not prove the job closed; availability_status remains unknown without
        evidence. Preserve freshness warnings and use canonical_url to apply.
        """
        return await self._call(self._service(ctx).get_job(job_id))


class JobReferenceTools(JobToolGroup):
    """JobReferenceTools look up the county and category names the job filters accept."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.list_regions)
        self._add_tool(server, self.list_categories)

    async def list_regions(self, ctx: Context) -> list[RegionDTO]:
        """Look up valid Croatian county names and codes for other tools' county filters.

        Use when a county label is uncertain or the user asks which counties are
        supported. Returns reference names, codes, open-ad counts and freshness.
        For "Gdje ima najviše poslova?" use show_jobs_by_county directly; this
        lookup is not the user-facing geographic comparison workflow.
        """
        return list(await self._call(self._service(ctx).list_regions()))

    async def list_categories(self, ctx: Context) -> list[CategoryDTO]:
        """Look up valid occupation-category names for the category filter.

        Use when a category name is uncertain or the user asks for supported
        categories. Returns names and open-ad counts. Prefer query keywords for
        broad occupation searches, since jobs with unknown categories would be
        excluded by category. For finding jobs use show_jobs; for market
        breakdowns use job_market_stats.
        """
        return list(await self._call(self._service(ctx).list_categories()))
