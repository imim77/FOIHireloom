from collections.abc import Awaitable
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig
from fastmcp.exceptions import ToolError
from pydantic import Field

from FOIHireloom.dto.job_comparison import (
    MAX_COMPARED_JOBS,
    MIN_COMPARED_JOBS,
    JobComparisonConditionsDTO,
    JobComparisonDTO,
    JobComparisonViewDTO,
)
from FOIHireloom.dto.accommodation_comparison import AccommodationComparisonDTO
from FOIHireloom.dto.job_market import (
    DEFAULT_MARKET_TOP,
    MAX_MARKET_TOP,
    CountyMetric,
    JobMarketFiltersDTO,
    JobMarketStatsDTO,
    JobsByCountyDTO,
)
from FOIHireloom.dto.job_search import (
    MAX_PAGE_SIZE,
    CategoryDTO,
    JobCardsDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError, PersistenceError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .apps import accommodation_comparison, job_cards, job_comparison, jobs_by_county
from .apps.views import ACCOMMODATION_COMPARISON, JOB_CARDS, JOB_COMPARISON, JOBS_BY_COUNTY
from .job_filters import (
    CATEGORY_DESCRIPTION, Accommodation, ContractFilter, Education, EmploymentTags,
    FullTime, MaxExperienceMonths, Place, SearchQuery, Skills,
)
from .tool_provider import DATA_ONLY, READ_ONLY, ToolGroup

# Key of the search service in the server's lifespan context.
JOB_SEARCH_SERVICE = "job_search_service"

# The arguments of the tools that compare jobs: the jobs and the conditions the user states about themselves.
ComparedJobIds = Annotated[list[Annotated[int, Field(ge=1, le=2**63 - 1)]], Field(
    min_length=MIN_COMPARED_JOBS, max_length=MAX_COMPARED_JOBS,
    description="ids of the 2 or 3 jobs to compare, each once, from earlier search_jobs or show_jobs results, in the "
                "order to show them.",
)]
UserExperience = Annotated[MaxExperienceMonths, Field(
    description="The user's experience in months. A job meets it when it asks for at most that; with 0 only jobs "
                "that need none ('Nije važno') and trainee ads do.",
)]
UserContract = Annotated[ContractFilter, Field(
    description="The contract the user wants: 'permanent' (na neodređeno), 'fixed_term' (na određeno) or 'other' "
                "(other forms of work).",
)]
UserFullTime = Annotated[FullTime, Field(
    description="true when the user wants a full-time job, false when they want a part-time one (under 40 hours a "
                "week).",
)]
UserEducation = Annotated[Education, Field(
    description="The user's education level; a job meets it when it accepts that level: 'primary_lower' (lower "
                "primary grades), 'primary' (primary school), 'secondary_3' (3-year secondary school), 'secondary_4' "
                "(4-year secondary school), 'college' (viša or bachelor's) or 'university' (faculty, master's or "
                "doctorate).",
)]
UserAccommodation = Annotated[Accommodation, Field(
    description="true when the user needs accommodation, met by jobs offering any (shared, single or family); false "
                "when the user wants a job that offers none.",
)]


class JobTools(ToolGroup):
    """MCP tools over stored HZZ job advertisements.

    Tools only translate arguments and errors; JobSearchService holds the
    rules. The server's lifespan must provide the service under
    JOB_SEARCH_SERVICE. Raw search and comparison endpoints remain app-only;
    user requests go to the corresponding show_ workflows by default.
    """

    def register(self, server: FastMCP) -> None:
        @server.tool(app=DATA_ONLY, annotations=READ_ONLY)
        async def search_jobs(
            ctx: Context,
            query: SearchQuery = None,
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
            filters = JobSearchFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, skills=skills, include_expired=include_expired, limit=limit,
                cursor=cursor,
            )
            return await self._call(service(ctx).search(filters))

        @server.tool(app=AppConfig(resource_uri=JOB_CARDS.uri), annotations=READ_ONLY)
        async def show_jobs(
            ctx: Context,
            query: SearchQuery = None,
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
            filters = JobSearchFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, skills=skills, include_expired=include_expired, limit=limit,
                cursor=cursor,
            )
            return job_cards.job_cards(await self._call(service(ctx).search_cards(filters)), filters)

        @server.tool(annotations=READ_ONLY)
        async def job_market_stats(
            ctx: Context,
            query: SearchQuery = None,
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
            skills: Skills = None,
            include_expired: Annotated[bool, Field(
                description="Also count jobs whose application deadline has passed.",
            )] = False,
            top: Annotated[int, Field(
                ge=1, le=MAX_MARKET_TOP, description="Entries in the employers list.",
            )] = DEFAULT_MARKET_TOP,
        ) -> JobMarketStatsDTO:
            """Count matching job ads and summarize employers, contracts, education and other job conditions.

            Use for totals and general labour-market breakdowns: "Koliko ima oglasa
            za kuhare u Istri?", "Koji poslodavci najviše zapošljavaju?", "Koliki je
            udio ugovora na neodređeno?" or "How many jobs are available?".
            Choose by the question's subject:
            - Where jobs or workers are concentrated across counties: show_jobs_by_county.
            - Counts, shares or distribution by accommodation: show_accommodation_comparison.
            - Specific counties compared with unemployment: show_county_comparison.
            - Individual job recommendations or browsing: show_jobs.
            These choices do not require the user to ask for a chart or cards.

            Returns totals, workers sought, breakdowns, freshness and unknown-condition
            counts for all matching stored HZZ ads, not just one page. One ad may seek
            several workers. Categories cover with_category ads; normalized conditions
            cover only known values. Multi-valued tags or education can count one ad
            in several groups. Shares must name their denominator. published_recently
            and closing_soon use window_days relative to today. Report unknown_total
            and coverage.warning. Null or unreported conditions are never negative answers.
            """
            filters = JobMarketFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, skills=skills, include_expired=include_expired, top=top,
            )
            return await self._call(service(ctx).market_stats(filters))

        @server.tool(app=AppConfig(resource_uri=ACCOMMODATION_COMPARISON.uri), annotations=READ_ONLY)
        async def show_accommodation_comparison(
            ctx: Context,
            query: SearchQuery = None,
            county: Annotated[str | None, Field(
                description="County code or name from list_regions; leave out for all counties.")] = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            skills: Skills = None,
            include_expired: Annotated[bool, Field(description="Also include ads whose deadline has passed.")] = False,
        ) -> AccommodationComparisonDTO:
            """Count and compare job ads offering accommodation, not offering it, or leaving it unknown.

            DEFAULT for accommodation counts, percentages and distributions, including
            "Koliko oglasa za kuhare u Varaždinskoj nudi smještaj?", "Koliki udio
            poslova u Istri ima smještaj?" and "How many jobs offer accommodation?".
            Call directly even when the user never says "graf", "chart", "usporedba"
            or a tool name. Do not ask for a format, count a search page or select
            example jobs. Automatically presents the distribution and returns its data.

            For cooks in Varaždinska use query='kuhar', county='varazdinska'. Counts
            all matching ads in three groups: offered (shared/single/family), explicitly
            not offered (none), unknown. Shares use all matching ads, not workers.
            There is no accommodation filter because all three groups must remain
            in the population. Preserve unknown values, coverage_note and unknown_note.

            A request to FIND a job with accommodation, such as "Tražim posao kuhara
            sa smještajem", belongs to show_jobs(query='kuhar', accommodation=true).
            This tool answers aggregate questions, not recommendations of individual jobs.
            """
            filters = JobMarketFiltersDTO(
                query=query, county=county, category=category, max_experience_months=max_experience_months,
                contract=contract, full_time=full_time, education=education, employment_tags=employment_tags,
                place=place, skills=skills, include_expired=include_expired,
            )
            stats = await self._call(service(ctx).market_stats(filters))
            return accommodation_comparison.accommodation_comparison(stats, filters)

        @server.tool(app=AppConfig(resource_uri=JOBS_BY_COUNTY.uri), annotations=READ_ONLY)
        async def show_jobs_by_county(
            ctx: Context,
            query: SearchQuery = None,
            category: Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)] = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            skills: Skills = None,
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
            """Find which Croatian counties have the most job ads or seek the most workers.

            DEFAULT for geographic job distribution, county rankings and where demand
            is highest: "Gdje ima najviše poslova za kuhare?", "U kojim županijama
            se najviše zapošljava?", "Koja županija traži najviše radnika?" and
            "Where are most nursing jobs?". Call directly without requiring "graf",
            "chart", "prikaži" or a chosen format. Automatically presents a county
            ranking and returns the counts for every matching county.

            Use metric='jobs' for ads and metric='workers_needed' for workers or
            positions; one ad may seek several workers. query and condition filters
            select the occupation and requirements. top limits initially visible
            counties, not the counted population. share is a percentage of total_jobs.
            Report coverage_note and unknown_note; missing conditions stay unknown.

            For a comparison of named counties including DZS unemployment use
            show_county_comparison. For actual job vacancies use show_jobs; for
            accommodation shares use show_accommodation_comparison. General totals
            or employer/contract breakdowns belong to job_market_stats.
            """
            filters = JobMarketFiltersDTO(
                query=query, category=category, max_experience_months=max_experience_months, contract=contract,
                full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, skills=skills, include_expired=include_expired,
            )
            stats = await self._call(service(ctx).market_stats(filters))
            return jobs_by_county.jobs_by_county(stats, top, filters, metric)

        @server.tool(annotations=READ_ONLY)
        async def get_job(
            ctx: Context,
            job_id: Annotated[int, Field(ge=1, le=2**63 - 1, description="id of a job from earlier show_jobs results.")],
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
            return await self._call(service(ctx).get_job(job_id))

        @server.tool(app=DATA_ONLY, annotations=READ_ONLY)
        async def compare_jobs(
            ctx: Context,
            job_ids: ComparedJobIds,
            max_experience_months: UserExperience = None,
            contract: UserContract = None,
            full_time: UserFullTime = None,
            education: UserEducation = None,
            accommodation: UserAccommodation = None,
        ) -> JobComparisonDTO:
            """App-only data comparison endpoint. For a user's selected ads use show_job_comparison.

            show_job_comparison returns the same comparison with an automatic table;
            use it for "Usporedi prvi i treći oglas" without requiring a format request.
            This endpoint remains callable for app workflows that consume raw rows.
            Compare 2 or 3 distinct known IDs in the user's order. Conditions must be
            stated by the user, never guessed or inferred. Report unknown as unknown;
            a match describes the advertisement, never that the employer will accept the user.
            Market-wide accommodation counts belong to show_accommodation_comparison.
            """
            conditions = JobComparisonConditionsDTO(
                max_experience_months=max_experience_months, contract=contract, full_time=full_time,
                education=education, accommodation=accommodation,
            )
            return await self._compare(ctx, job_ids, conditions)

        @server.tool(app=AppConfig(resource_uri=JOB_COMPARISON.uri), annotations=READ_ONLY)
        async def show_job_comparison(
            ctx: Context,
            job_ids: ComparedJobIds,
            max_experience_months: UserExperience = None,
            contract: UserContract = None,
            full_time: UserFullTime = None,
            education: UserEducation = None,
            accommodation: UserAccommodation = None,
        ) -> JobComparisonViewDTO:
            """Compare 2 or 3 specific job advertisements selected by the user against their stated conditions.

            DEFAULT for "Usporedi prvi i treći oglas", "Koji je od ova dva posla
            prikladniji za mene?" and "Compare these jobs". Call directly with their
            known job_ids in selection order. The user does not need to ask for a
            table, cards or any display format. Automatically presents a side-by-side
            comparison and also returns the data. If the selected ads cannot be
            identified from the conversation, ask which ads to compare; never invent IDs.

            Pass only the user's stated conditions, never guessed or inferred ones.
            Returns rows for experience, education, contract, working time,
            accommodation and deadline, with evidence and per-condition verdicts.
            Report 'unknown' as unknown; a match describes what the ad states,
            never that the employer will accept the user. Expired or unread ads may
            still be compared. Use canonical_url for full advertisements or applications.

            Do not select a few ads to answer an aggregate question. Accommodation
            counts or shares belong to show_accommodation_comparison; comparing
            counties belongs to show_county_comparison; finding new jobs to show_jobs.
            """
            conditions = JobComparisonConditionsDTO(
                max_experience_months=max_experience_months, contract=contract, full_time=full_time,
                education=education, accommodation=accommodation,
            )
            return job_comparison.job_comparison(await self._compare(ctx, job_ids, conditions))

        @server.tool(annotations=READ_ONLY)
        async def list_regions(ctx: Context) -> list[RegionDTO]:
            """Look up valid Croatian county names and codes for other tools' county filters.

            Use when a county label is uncertain or the user asks which counties are
            supported. Returns reference names, codes, open-ad counts and freshness.
            For "Gdje ima najviše poslova?" use show_jobs_by_county directly; this
            lookup is not the user-facing geographic comparison workflow.
            """
            return list(await self._call(service(ctx).list_regions()))

        @server.tool(annotations=READ_ONLY)
        async def list_categories(ctx: Context) -> list[CategoryDTO]:
            """Look up valid occupation-category names for the category filter.

            Use when a category name is uncertain or the user asks for supported
            categories. Returns names and open-ad counts. Prefer query keywords for
            broad occupation searches, since jobs with unknown categories would be
            excluded by category. For finding jobs use show_jobs; for market
            breakdowns use job_market_stats.
            """
            return list(await self._call(service(ctx).list_categories()))

    async def _compare(
        self, ctx: Context, job_ids: list[int], conditions: JobComparisonConditionsDTO,
    ) -> JobComparisonDTO:
        # The service compares without conditions when none is set; pass that as None.
        stated = conditions if conditions.model_dump(exclude_none=True) else None
        return await self._call(service(ctx).compare_jobs(job_ids, stated))

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
