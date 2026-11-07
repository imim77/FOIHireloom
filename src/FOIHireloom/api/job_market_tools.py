from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from FOIHireloom.dto.accommodation_comparison import AccommodationComparisonDTO
from FOIHireloom.dto.job_market import (
    DEFAULT_MARKET_TOP,
    MAX_MARKET_TOP,
    CountyMetric,
    JobMarketFiltersDTO,
    JobMarketStatsDTO,
    JobsByCountyDTO,
)

from .apps import accommodation_comparison, jobs_by_county
from .apps.views import ACCOMMODATION_COMPARISON, JOBS_BY_COUNTY
from .job_filters import (
    Accommodation, Category, ContractFilter, County, Education, EmploymentTags,
    FullTime, MaxExperienceMonths, Place, SearchQuery, Skills,
)
from .job_tools import JobToolGroup
from .tool_provider import tool_arguments


class JobMarketTools(JobToolGroup):
    """JobMarketTools count all matching job ads, as totals and breakdowns, by accommodation or by county."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.job_market_stats)
        self._add_tool(server, self.show_accommodation_comparison, app=ACCOMMODATION_COMPARISON.app_config)
        self._add_tool(server, self.show_jobs_by_county, app=JOBS_BY_COUNTY.app_config)

    async def job_market_stats(
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
        filters = JobMarketFiltersDTO(**tool_arguments(locals()))
        return await self._call(self._service(ctx).market_stats(filters))

    async def show_accommodation_comparison(
        self,
        ctx: Context,
        query: SearchQuery = None,
        county: Annotated[str | None, Field(
            description="County code or name from list_regions; leave out for all counties.")] = None,
        category: Category = None,
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
        filters = JobMarketFiltersDTO(**tool_arguments(locals()))
        stats = await self._call(self._service(ctx).market_stats(filters))
        return accommodation_comparison.accommodation_comparison(stats, filters)

    async def show_jobs_by_county(
        self,
        ctx: Context,
        query: SearchQuery = None,
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
        filters = JobMarketFiltersDTO(**tool_arguments(locals(), "top", "metric"))
        stats = await self._call(self._service(ctx).market_stats(filters))
        return jobs_by_county.jobs_by_county(stats, top, filters, metric)
