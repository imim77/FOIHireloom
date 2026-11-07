import socket
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from FOIHireloom.config.settings import Settings
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .app_views import AppViews
from .apps.views import BUILD_HINT, stale_sources
from .county_tools import COUNTY_INDICATOR_SERVICE, CountyComparisonTools, UnemploymentHistoryTools
from .forecast_tools import LABOUR_FORECAST_SERVICE, ForecastTools
from .job_comparison_tools import JobComparisonTools
from .job_market_tools import JobMarketTools
from .job_tools import JOB_SEARCH_SERVICE, JobDetailTools, JobReferenceTools, JobSearchTools
from .tool_provider import ToolGroup

INSTRUCTIONS = """Help users find Croatian HZZ job ads and understand HZZ/DZS labour-market data.
Choose tools by the user's task, not by whether they ask for a visual format.
The show_ tools are the default user-facing workflows: they return structured data
AND automatically present the appropriate cards, ranking, comparison or history
on MCP Apps hosts. Use them even for ordinary questions. Never ask the user to
say "kao graf", "kao kartice", "chart", "table" or choose a display format first.

Route by intent:
- Find or browse individual vacancies, including jobs with accommodation or no
  experience -> show_jobs. Example: "Tražim posao kuhara sa smještajem" means
  query='kuhar', accommodation=true. Use get_job for details of one known ad.
- Where jobs are concentrated or which counties seek the most workers ->
  show_jobs_by_county. Use metric='jobs' for ads, 'workers_needed' for workers.
- Compare accommodation counts, shares or offered/not-offered/unknown groups ->
  show_accommodation_comparison, directly over all matching ads. Never count a
  search page or choose a few example jobs to answer an aggregate question.
- Compare 2 to 6 named counties by demand and registered unemployment ->
  show_county_comparison. A question about changes over time instead goes to
  show_unemployment_history (1 to 6 counties, 12 to 24 months).
- Forecast future county unemployment, employment or job ads ->
  show_labour_market_forecast for the named county. Return the Amazon Chronos model estimate with its
  80% interval; use show_unemployment_history for past values.
- Compare 2 or 3 particular ads selected by the user -> show_job_comparison with
  those known IDs in the user's order. Ask which ads only if selection is unclear.
- Other totals and employer/contract/education breakdowns -> job_market_stats.
  County rankings and accommodation distributions use the dedicated workflows above.

search_jobs, compare_jobs, compare_counties, unemployment_history and forecast_labour_market are app-only
raw-data counterparts, not alternative user-facing workflows. Their presence in
an older client's catalog is not a reason to choose them over the show_ tools.
list_regions and list_categories resolve unknown filter values; they are reference
lookups, not substitutes for a job search or a geographic comparison.

Extract only stated conditions into dedicated filters; do not guess preferences
or insert filter words into query. Omit expired ads unless requested. For missing
required counties or selected job IDs ask for that information, not for a format.
The server reads stored data, never live HZZ/DZS. Preserve freshness warnings,
unknown values, sources, provisional flags and distinct HZZ/DZS reference dates.
Unknown accommodation is not "no accommodation"; missing values are not zero.
County-wide ratios never use only one occupation's ads. Use canonical_url to
read the original advertisement or apply; do not invent facts or promise employment.
"""

# Every group the server registers, in the order clients list their tools and pages.
TOOL_GROUPS: tuple[ToolGroup, ...] = (
    JobSearchTools(), JobMarketTools(), JobDetailTools(), JobComparisonTools(), JobReferenceTools(),
    CountyComparisonTools(), UnemploymentHistoryTools(), ForecastTools(), AppViews(),
)


class McpServer:
    """FastMCP server whose tools share one search, county indicator and forecast service while it runs.

    The services, and their database engines, open when the server starts
    and close when it stops. Pass job_search_service,
    county_indicator_service or labour_forecast_service to supply another
    one, for example in tests. Settings choose the transport: stdio, or Streamable
    HTTP with a /health route for hosting platforms.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        job_search_service: ServiceOpener[JobSearchServiceInterface] | None = None,
        county_indicator_service: ServiceOpener[CountyIndicatorServiceInterface] | None = None,
        labour_forecast_service: ServiceOpener[LabourMarketForecastServiceInterface] | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._dependencies = DependencyService(self._settings)
        self._job_search_service = job_search_service
        self._county_indicator_service = county_indicator_service
        self._labour_forecast_service = labour_forecast_service
        # Unexpected errors reach the client without details; tools raise ToolError for the rest.
        self._server = FastMCP("FOIHireloom", instructions=INSTRUCTIONS, lifespan=self._lifespan,
                               mask_error_details=True)
        for group in TOOL_GROUPS:
            group.register(self._server)
        self._server.custom_route("/health", methods=["GET"], include_in_schema=False)(self._health)

    @property
    def server(self) -> FastMCP:
        return self._server

    @asynccontextmanager
    async def _lifespan(self, server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with self._dependencies.read_services(
            job_search=self._job_search_service, county_indicators=self._county_indicator_service,
            labour_forecast=self._labour_forecast_service,
        ) as (search, indicators, forecast):
            yield {JOB_SEARCH_SERVICE: search, COUNTY_INDICATOR_SERVICE: indicators, LABOUR_FORECAST_SERVICE: forecast}

    @staticmethod
    async def _health(request: Request) -> Response:
        """Report that the process serves requests; it does not query the database."""
        return JSONResponse({"status": "ok"})

    def run(self) -> None:
        if stale := stale_sources():
            print(f"Warning: the MCP App pages are older than {', '.join(stale)}; {BUILD_HINT}.", file=sys.stderr)
        if self._settings.MCP_TRANSPORT == "stdio":
            print("Starting MCP server", file=sys.stderr)
            self._server.run("stdio")
        else:
            self._server.run("http", host=self._settings.MCP_HOST, port=self._settings.MCP_PORT,
                            **self._http_options())

    async def run_http_async(self, sockets: list[socket.socket] | None = None) -> None:
        """Serve Streamable HTTP until cancelled; sockets replace host and port when given."""
        await self._server.run_http_async(host=self._settings.MCP_HOST, port=self._settings.MCP_PORT,
                                         sockets=sockets, **self._http_options())

    def _http_options(self) -> dict[str, Any]:
        # "auto" checks the Host and Origin headers of a server reachable via
        # localhost, which blocks DNS rebinding from web pages. Listed hosts
        # are allowed in addition to localhost and are then always checked.
        return {
            "path": self._settings.MCP_PATH,
            "host_origin_protection": "auto",
            "allowed_hosts": self._settings.MCP_ALLOWED_HOSTS or None,
        }
