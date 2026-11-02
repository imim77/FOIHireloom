from collections.abc import Awaitable
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig
from fastmcp.exceptions import ToolError
from pydantic import Field

from FOIHireloom.dto.county_indicators import (
    DEFAULT_HISTORY_MONTHS,
    MAX_COMPARED_COUNTIES,
    MAX_HISTORY_COUNTIES,
    MAX_HISTORY_MONTHS,
    MIN_COMPARED_COUNTIES,
    MIN_HISTORY_MONTHS,
    CountyComparisonDTO,
    CountyComparisonRequestDTO,
    CountyComparisonViewDTO,
    UnemploymentHistoryDTO,
    UnemploymentHistoryRequestDTO,
    UnemploymentHistoryViewDTO,
)
from FOIHireloom.dto.dzs import DzsSex
from FOIHireloom.dto.job_market import JobCountFiltersDTO
from FOIHireloom.dto.job_search import MAX_QUERY_LENGTH
from FOIHireloom.exceptions import InvalidIndicatorRequestError, InvalidJobSearchError, PersistenceError
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface

from .apps import county_comparison
from .apps import unemployment_history as history_view
from .apps.labels import active_filters
from .apps.views import COUNTY_COMPARISON, UNEMPLOYMENT_HISTORY
from .job_tools import (
    CATEGORY_DESCRIPTION,
    READ_ONLY,
    Accommodation,
    ContractFilter,
    Education,
    EmploymentTags,
    FullTime,
    MaxExperienceMonths,
    Place,
)
from .tool_provider import ToolGroup

# Key of the indicator service in the server's lifespan context.
COUNTY_INDICATOR_SERVICE = "county_indicator_service"

CountyLabel = Annotated[str, Field(min_length=1, max_length=100)]

# The arguments compare_counties and show_county_comparison share, besides the job filters of job_tools.
ComparedCounties = Annotated[list[CountyLabel], Field(
    min_length=MIN_COMPARED_COUNTIES, max_length=MAX_COMPARED_COUNTIES,
    description=f"{MIN_COMPARED_COUNTIES} to {MAX_COMPARED_COUNTIES} different counties to compare, as codes or names "
                "from list_regions, e.g. ['varazdinska', 'medimurska'], in the order to show them.",
)]
CountyQuery = Annotated[str | None, Field(
    max_length=MAX_QUERY_LENGTH,
    description="Words chosen as for search_jobs, e.g. 'kuhar'; leave out to count all jobs.",
)]
CountyCategory = Annotated[str | None, Field(description=CATEGORY_DESCRIPTION)]
CountyIncludeExpired = Annotated[bool, Field(
    description="Also count jobs whose application deadline has passed in filtered_jobs.",
)]
Period = Annotated[str | None, Field(
    pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    description="DZS reference month as YYYY-MM, e.g. '2026-09', only when the user asks for a month. Leave out to "
                "use, per indicator, the latest month known for every compared county.",
)]

# The arguments unemployment_history and show_unemployment_history share.
HistoryCounties = Annotated[list[CountyLabel], Field(
    min_length=1, max_length=MAX_HISTORY_COUNTIES,
    description=f"1 to {MAX_HISTORY_COUNTIES} different counties, as codes or names from list_regions, e.g. "
                "['varazdinska'].",
)]
HistoryMonths = Annotated[int, Field(
    ge=MIN_HISTORY_MONTHS, le=MAX_HISTORY_MONTHS,
    description=f"Months to show, {MIN_HISTORY_MONTHS} to {MAX_HISTORY_MONTHS}, ending with the latest month DZS has "
                "for every requested county.",
)]
HistorySex = Annotated[DzsSex, Field(description="Whose unemployment rate: 'total', 'women' or 'men'.")]


class CountyIndicatorTools(ToolGroup):
    """MCP tools comparing counties by HZZ job ads and DZS registered unemployment, with and without a view.

    Tools only translate arguments and errors; CountyIndicatorService holds
    the rules. The server's lifespan must provide the service under
    COUNTY_INDICATOR_SERVICE.
    """

    def register(self, server: FastMCP) -> None:
        @server.tool(annotations=READ_ONLY)
        async def compare_counties(
            ctx: Context,
            counties: ComparedCounties,
            query: CountyQuery = None,
            category: CountyCategory = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: CountyIncludeExpired = False,
            period: Period = None,
        ) -> CountyComparisonDTO:
            """Return the data of a comparison of 2 to 6 Croatian counties, without a view.

            When the user asks to compare counties, call show_county_comparison
            instead: it returns the same data and also shows it. Use this tool
            only when you need the numbers without showing them, e.g. to choose
            counties before showing a comparison. Per county:
            filtered_jobs counts the HZZ ads matching the job filters, which
            work as in job_market_stats: jobs, workers_needed with
            workers_needed_coverage (ads stating the number out of all; an
            unknown number is not 0), permanent_share (permanent contracts out
            of the ads whose contract is known; whole is that denominator)
            with contract_coverage, and closing_soon (deadline within
            window_days days). all_active_jobs are the same counts over every
            active ad of the county, ignoring the filters.
            unemployed, active_population and unemployment_rate are DZS values
            for their reference month (period, first day of the month), with
            is_provisional.

            The two indicators describe each county as a whole, never one
            occupation: unemployed_per_worker is registered unemployed divided
            by all_active_jobs.workers_needed, and jobs_per_1000_active is
            all_active_jobs.jobs per 1,000 active population. They do not use
            the job filters; report the filtered counts next to them, never
            divide the unemployed by one occupation's ads. Each gives the
            numerator and denominator used. A null value has an
            unavailable_reason: 'no_dzs_data' (no DZS import),
            'no_common_period', 'dzs_value_missing' (no value for that month;
            another month is never substituted), 'no_hzz_data' (the county's
            HZZ feeds were never loaded), 'no_known_workers' or
            'zero_denominator'. Say "the indicator is not available" and why;
            never show 0 or infinity instead.

            dzs_periods gives each DZS indicator's month, which may differ
            between indicators. HZZ counts are as of hzz_coverage.data_as_of
            and DZS values for a past month; tell the user both dates. Name
            the sources, mark 2026 months as provisional and pass on the
            notes, in particular that the indicators describe HZZ ads and
            registered unemployment, not the whole labour market or anyone's
            chance of employment. When hzz_coverage.warning is set, tell the
            user the HZZ counts may be outdated or incomplete. active_filters
            are the Croatian labels of the set filters.
            """
            filters = JobCountFiltersDTO(
                query=query, category=category, max_experience_months=max_experience_months, contract=contract,
                full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired,
            )
            return await self._compare(ctx, counties, filters, period)

        @server.tool(app=AppConfig(resource_uri=COUNTY_COMPARISON.uri), annotations=READ_ONLY)
        async def show_county_comparison(
            ctx: Context,
            counties: ComparedCounties,
            query: CountyQuery = None,
            category: CountyCategory = None,
            max_experience_months: MaxExperienceMonths = None,
            contract: ContractFilter = None,
            full_time: FullTime = None,
            education: Education = None,
            accommodation: Accommodation = None,
            employment_tags: EmploymentTags = None,
            place: Place = None,
            include_expired: CountyIncludeExpired = False,
            period: Period = None,
        ) -> CountyComparisonViewDTO:
            """Show the user 2 to 6 Croatian counties side by side by HZZ job ads and DZS registered unemployment.

            Use it whenever the user asks to compare counties, e.g. "compare
            demand for cooks in Varaždinska and Međimurska" or "where are the
            most unemployed per sought worker". Hosts that support
            MCP Apps draw a column per county with the ads matching the
            filters, the DZS values with their reference months and the two
            county-wide indicators, each unavailable value with its reason,
            next to the HZZ check time, the sources and the notes. Every host
            also gets the data, as in compare_counties, whose rules apply:
            the indicators describe each county as a whole, never the
            filtered ads; say "the indicator is not available" and why,
            never 0 or infinity; tell the user both dates and the sources.
            title, description, short_name, unavailable_label, coverage_note,
            source_links, view_notes and disclaimer are the Croatian wording
            the view shows.
            """
            filters = JobCountFiltersDTO(
                query=query, category=category, max_experience_months=max_experience_months, contract=contract,
                full_time=full_time, education=education, accommodation=accommodation,
                employment_tags=employment_tags, place=place, include_expired=include_expired,
            )
            return county_comparison.county_comparison(await self._compare(ctx, counties, filters, period))

        @server.tool(annotations=READ_ONLY)
        async def unemployment_history(
            ctx: Context,
            counties: HistoryCounties,
            months: HistoryMonths = DEFAULT_HISTORY_MONTHS,
            sex: HistorySex = "total",
        ) -> UnemploymentHistoryDTO:
            """Return the monthly registered unemployment rate of 1 to 6 counties (DZS), without a view.

            When the user asks how unemployment changed, call
            show_unemployment_history instead: it returns the same data and
            also draws a chart. Use this tool only when you need the numbers
            without showing them. Each county's
            series runs from first_period to last_period (first days of the
            months), oldest first; each point has the rate in percent with
            one decimal and is_provisional. A null rate has
            unavailable_reason 'dzs_value_missing'. latest is the last month,
            same_month_previous_year the same month a year earlier, and
            change_pp their difference in percentage points, null with
            change_unavailable_reason when either is unknown. Report the
            change in percentage points, not percent. Comparing with the same
            month a year earlier reduces seasonality but is not seasonal
            adjustment; months of 2026 are provisional, so mark them. Without
            DZS data, every series is empty and unavailable_reason says why.
            Name the sources and pass on the notes.
            """
            return await self._history(ctx, counties, months, sex)

        @server.tool(app=AppConfig(resource_uri=UNEMPLOYMENT_HISTORY.uri), annotations=READ_ONLY)
        async def show_unemployment_history(
            ctx: Context,
            counties: HistoryCounties,
            months: HistoryMonths = DEFAULT_HISTORY_MONTHS,
            sex: HistorySex = "total",
        ) -> UnemploymentHistoryViewDTO:
            """Show the user a line chart of the monthly registered unemployment rate of 1 to 6 counties (DZS).

            Use it whenever the user asks how unemployment changed, e.g. "how
            did unemployment in Varaždinska change over the last year". Hosts
            that
            support MCP Apps draw a line per county, with provisional months
            dashed and missing months as gaps, and per county the latest
            rate, the same month a year earlier and the change in percentage
            points, with the sources and the notes. Every host also gets the
            data, as in unemployment_history, whose rules apply: report the
            change in percentage points, mark 2026 months as provisional and
            say that comparing with the same month is not seasonal
            adjustment. title, description, short_name,
            change_unavailable_label, unavailable_label, source_links and
            view_notes are the Croatian wording the view shows.
            """
            return history_view.unemployment_history(await self._history(ctx, counties, months, sex))

    async def _compare(
        self, ctx: Context, counties: list[str], filters: JobCountFiltersDTO, period: str | None,
    ) -> CountyComparisonDTO:
        request = CountyComparisonRequestDTO(counties=tuple(counties), filters=filters, period=period)
        comparison = await self._call(service(ctx).compare_counties(request))
        return comparison.model_copy(update={"active_filters": active_filters(filters)})

    async def _history(self, ctx: Context, counties: list[str], months: int, sex: DzsSex) -> UnemploymentHistoryDTO:
        request = UnemploymentHistoryRequestDTO(counties=tuple(counties), months=months, sex=sex)
        return await self._call(service(ctx).unemployment_history(request))

    @staticmethod
    async def _call[T](operation: Awaitable[T]) -> T:
        """Turn errors the caller can act on into tool errors; database details stay in the server log."""
        try:
            return await operation
        except (InvalidIndicatorRequestError, InvalidJobSearchError) as error:
            raise ToolError(error.details) from error
        except PersistenceError as error:
            raise ToolError("County data is temporarily unavailable; try again later.") from error


def service(ctx: Context) -> CountyIndicatorServiceInterface:
    return ctx.lifespan_context[COUNTY_INDICATOR_SERVICE]
