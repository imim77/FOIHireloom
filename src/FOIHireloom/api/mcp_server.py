import socket
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from FOIHireloom.config.settings import Settings
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .job_tools import JOB_SEARCH_SERVICE, JobTools

INSTRUCTIONS = (
    "Search job advertisements from the Croatian Employment Service (HZZ). "
    "Jobs come from HZZ county RSS feeds and the jobs' HZZ pages, which this server imports regularly; "
    "the tools read the stored copy and never contact HZZ. Use list_regions and "
    "list_categories for valid filter values, search_jobs to list jobs and "
    "job_market_stats for counts and breakdowns. When a result carries a "
    "coverage warning, pass it on to the user. Send users to canonical_url to "
    "read the full advertisement or apply."
)

type JobSearchServiceOpener = Callable[[], AbstractAsyncContextManager[JobSearchServiceInterface]]


class McpServer:
    """FastMCP server whose tools share one search service while it runs.

    The service, and its database engine, opens when the server starts and
    closes when it stops. Pass job_search_service to supply another one, for
    example in tests. Settings choose the transport: stdio, or Streamable
    HTTP with a /health route for hosting platforms.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        job_search_service: JobSearchServiceOpener | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._job_search_service = job_search_service or DependencyService(self._settings).job_search_service
        # Unexpected errors reach the client without details; tools raise ToolError for the rest.
        self.server = FastMCP("FOIHireloom", instructions=INSTRUCTIONS, lifespan=self._lifespan,
                              mask_error_details=True)
        for group in (JobTools(),):
            group.register(self.server)
        self.server.custom_route("/health", methods=["GET"], include_in_schema=False)(self._health)

    @asynccontextmanager
    async def _lifespan(self, server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with self._job_search_service() as service:
            yield {JOB_SEARCH_SERVICE: service}

    @staticmethod
    async def _health(request: Request) -> Response:
        """Report that the process serves requests; it does not query the database."""
        return JSONResponse({"status": "ok"})

    def run(self) -> None:
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
