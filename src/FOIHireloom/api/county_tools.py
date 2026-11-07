from typing import Annotated

from fastmcp import Context, FastMCP
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
from FOIHireloom.exceptions import InvalidIndicatorRequestError, InvalidJobSearchError
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface

from .apps import county_comparison
from .apps import unemployment_history as history_view
from .apps.labels import active_filters
from .apps.views import COUNTY_COMPARISON, UNEMPLOYMENT_HISTORY
from .job_filters import (
    Accommodation,
    Category,
    ContractFilter,
    Education,
    EmploymentTags,
    FullTime,
    MaxExperienceMonths,
    Place,
    SearchQuery,
    Skills,
)
from .tool_provider import DATA_ONLY, ServiceToolGroup, tool_arguments

# Key of the indicator service in the server's lifespan context.
COUNTY_INDICATOR_SERVICE = "county_indicator_service"

CountyLabel = Annotated[str, Field(min_length=1, max_length=100)]

# The arguments compare_counties and show_county_comparison share, besides the shared job filters.
ComparedCounties = Annotated[list[CountyLabel], Field(
    min_length=MIN_COMPARED_COUNTIES, max_length=MAX_COMPARED_COUNTIES,
    description=f"{MIN_COMPARED_COUNTIES} to {MAX_COMPARED_COUNTIES} different counties to compare, as codes or names "
                "from list_regions, e.g. ['varazdinska', 'medimurska'], in the order to show them.",
)]
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


class CountyToolGroup(ServiceToolGroup[CountyIndicatorServiceInterface]):
    """CountyToolGroup is a group of MCP tools over HZZ job ads and DZS registered unemployment by county.

    The server's lifespan must provide CountyIndicatorService under
    COUNTY_INDICATOR_SERVICE.

    The data-only tools are visible to apps, not to the model: Claude picked
    compare_counties over show_county_comparison even when told otherwise,
    and the show_ tools return the same data. Hosts without MCP Apps ignore
    visibility and list both.
    """

    _service_key = COUNTY_INDICATOR_SERVICE
    _caller_errors = (InvalidIndicatorRequestError, InvalidJobSearchError)
    _unavailable_message = "County data is temporarily unavailable; try again later."


class CountyComparisonTools(CountyToolGroup):
    """CountyComparisonTools compare 2 to 6 counties by job demand and registered unemployment."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.compare_counties, app=DATA_ONLY)
        self._add_tool(server, self.show_county_comparison, app=COUNTY_COMPARISON.app_config)

    async def compare_counties(
        self,
        ctx: Context,
        counties: ComparedCounties,
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
        include_expired: CountyIncludeExpired = False,
        period: Period = None,
    ) -> CountyComparisonDTO:
        """App-only county data endpoint. For user county comparisons use show_county_comparison.

        show_county_comparison returns the same HZZ/DZS data with an automatic
        comparison, even without a request for a table or chart. This endpoint
        remains callable by apps consuming raw county data. Compare 2 to 6 distinct
        county codes or names. Job filters apply only to filtered_jobs; the
        indicators always use all_active_jobs. Missing values remain null with
        unavailable_reason. Preserve HZZ check times, DZS reference periods,
        sources and provisional flags; indicators describe county-wide statistics.
        """
        filters = JobCountFiltersDTO(**tool_arguments(locals(), "counties", "period"))
        return await self._compare(ctx, counties, filters, period)

    async def show_county_comparison(
        self,
        ctx: Context,
        counties: ComparedCounties,
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
        include_expired: CountyIncludeExpired = False,
        period: Period = None,
    ) -> CountyComparisonViewDTO:
        """Compare job demand and registered unemployment in 2 to 6 Croatian counties.

        DEFAULT when the user compares named counties or asks about county-wide
        unemployment relative to jobs: "Usporedi Istru i Varaždinsku", "Kakva je
        potražnja za kuharima u Varaždinskoj i Međimurskoj?" or "Compare jobs and
        unemployment in Zagreb and Split-Dalmatia". Call directly; the user does
        not need to say "tablica", "graf", "prikaži" or pick a format.
        Automatically presents a county comparison and returns its data.

        Pass distinct county codes or names in the requested order. Use query
        and job-condition filters only when stated. period selects a requested
        DZS month (YYYY-MM); otherwise use the latest common month per indicator.
        Returns filtered and all-active HZZ ad/worker counts, DZS unemployed,
        active population, unemployment rate and county-wide ratios. Indicators
        always use all_active_jobs, never just one occupation's ads. Preserve
        unavailable reasons, provisional flags, sources and both data dates;
        unknown is not zero. These statistics do not predict personal employment chances.

        For an all-county ranking by jobs or workers use show_jobs_by_county.
        For unemployment changes over time use show_unemployment_history.
        For individual job vacancies use show_jobs.
        """
        filters = JobCountFiltersDTO(**tool_arguments(locals(), "counties", "period"))
        return county_comparison.county_comparison(await self._compare(ctx, counties, filters, period))

    async def _compare(
        self, ctx: Context, counties: list[str], filters: JobCountFiltersDTO, period: str | None,
    ) -> CountyComparisonDTO:
        request = CountyComparisonRequestDTO(counties=tuple(counties), filters=filters, period=period)
        comparison = await self._call(self._service(ctx).compare_counties(request))
        return comparison.model_copy(update={"active_filters": active_filters(filters)})


class UnemploymentHistoryTools(CountyToolGroup):
    """UnemploymentHistoryTools return 1 to 6 counties' monthly registered unemployment rate."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.unemployment_history, app=DATA_ONLY)
        self._add_tool(server, self.show_unemployment_history, app=UNEMPLOYMENT_HISTORY.app_config)

    async def unemployment_history(
        self,
        ctx: Context,
        counties: HistoryCounties,
        months: HistoryMonths = DEFAULT_HISTORY_MONTHS,
        sex: HistorySex = "total",
    ) -> UnemploymentHistoryDTO:
        """App-only unemployment-series endpoint. For user trend questions use show_unemployment_history.

        show_unemployment_history returns the same DZS observations with an
        automatic time-series view, without a graph request. This endpoint
        remains callable for app workflows consuming raw monthly values.
        Accepts 1 to 6 counties and 12 to 24 months. Null rates are missing data;
        changes are percentage points, not percentages. Preserve sources,
        reference months and provisional flags.
        """
        return await self._history(ctx, counties, months, sex)

    async def show_unemployment_history(
        self,
        ctx: Context,
        counties: HistoryCounties,
        months: HistoryMonths = DEFAULT_HISTORY_MONTHS,
        sex: HistorySex = "total",
    ) -> UnemploymentHistoryViewDTO:
        """Track how registered unemployment changed over the last 12 to 24 months in Croatian counties.

        DEFAULT for unemployment history, trends, increases or decreases:
        "Kako se kretala nezaposlenost u Istri zadnjih godinu dana?",
        "Je li nezaposlenost u Varaždinskoj pala?", "Usporedi kretanje
        nezaposlenosti u Istri i Zagrebu" or "How has unemployment changed?".
        Call directly; the user does not need to ask for a graph, chart or format.
        Automatically presents monthly rates over time and returns the same data.

        Pass 1 to 6 distinct counties. Default months=12 and sex='total'; use
        months=24 for two years, sex='women' or 'men' only when requested.
        If the county cannot be identified, ask which county; do not invent one.
        Returns monthly DZS rates, the latest rate, the same month a year earlier
        and change_pp. Report changes in percentage points, preserve gaps and
        provisional flags, name sources and reference months. A year-on-year
        comparison is not seasonal adjustment. Missing observations are not zero.

        For current job demand compared with unemployment in named counties use
        show_county_comparison. For where job ads are concentrated use show_jobs_by_county.
        """
        return history_view.unemployment_history(await self._history(ctx, counties, months, sex))

    async def _history(self, ctx: Context, counties: list[str], months: int, sex: DzsSex) -> UnemploymentHistoryDTO:
        request = UnemploymentHistoryRequestDTO(counties=tuple(counties), months=months, sex=sex)
        return await self._call(self._service(ctx).unemployment_history(request))
