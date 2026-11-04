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
from .county_tools import COUNTY_INDICATOR_SERVICE, CountyIndicatorTools
from .forecast_tools import LABOUR_FORECAST_SERVICE, ForecastTools
from .job_tools import JOB_SEARCH_SERVICE, JobTools

INSTRUCTIONS = (
    "Search job advertisements from the Croatian Employment Service (HZZ). "
    "Jobs come from HZZ county RSS feeds and the jobs' HZZ pages, which this server imports regularly; "
    "the tools read the stored copy and never contact HZZ. Use list_regions and "
    "list_categories for valid filter values, search_jobs to list jobs and "
    "job_market_stats for counts and breakdowns. To show the user jobs as "
    "cards use show_jobs, and show_jobs_by_county for a chart of where the "
    "jobs are. For accommodation counts, shares or charts ('usporedba smještaja', 'sa smještajem i bez smještaja'), "
    "call show_accommodation_comparison directly, optionally with a county, query or category. "
    "Choose this view automatically from the user's question, even if they never say 'chart', 'show', "
    "'compare' or a tool name; do not ask them to choose a chart type. For example, "
    "'Koliko oglasa za kuhare u Varaždinskoj županiji nudi smještaj, a koliko ne?' means "
    "show_accommodation_comparison(query='kuhar', county='varazdinska'). "
    "It compares all matching ads in three groups: offered, explicitly not offered and unknown. "
    "A request to find or browse jobs with accommodation still uses search_jobs or show_jobs "
    "with accommodation=True; infer the chart for aggregate questions about counts, shares or distribution. "
    "For example, 'Prikaži usporedbu oglasa koji nude smještaj, ne nude smještaj i nemaju podatak o smještaju "
    "za kuhare u Varaždinskoj županiji' means show_accommodation_comparison(query='kuhar', county='varazdinska'). "
    "Do not search for and pick a few example ads for this aggregate question. "
    "Only when the user explicitly picked 2 or 3 particular jobs, pass their ids to "
    "show_job_comparison to show the user a comparison table, or to compare_jobs "
    "when only the data is needed; pass only the conditions the user stated. "
    "When the user asks to compare counties by job ads and DZS registered unemployment, call "
    "show_county_comparison; when the user asks how unemployment changed over the last 12 to 24 months, call "
    "show_unemployment_history. Both return the data and show it; compare_counties and unemployment_history "
    "return the same data without a view, only for when you need the numbers without showing them. Their indicators describe each county as a whole, and HZZ and DZS data refer to different dates, "
    "so name both. "
    "When the user asks about the future, e.g. how unemployment will develop or how many jobs will be needed, "
    "call forecast_labour_market; it returns an Amazon Chronos model forecast with an 80% interval. "
    "When a result carries a coverage warning, pass it on to the "
    "user. Send users to canonical_url to read the full advertisement or apply."
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
        self.server = FastMCP("FOIHireloom", instructions=INSTRUCTIONS, lifespan=self._lifespan,
                              mask_error_details=True)
        for group in (JobTools(), CountyIndicatorTools(), ForecastTools(), AppViews()):
            group.register(self.server)
        self.server.custom_route("/health", methods=["GET"], include_in_schema=False)(self._health)

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
            self.server.run("stdio")
        else:
            self.server.run("http", host=self._settings.MCP_HOST, port=self._settings.MCP_PORT,
                            **self._http_options())

    async def run_http_async(self, sockets: list[socket.socket] | None = None) -> None:
        """Serve Streamable HTTP until cancelled; sockets replace host and port when given."""
        await self.server.run_http_async(host=self._settings.MCP_HOST, port=self._settings.MCP_PORT,
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
