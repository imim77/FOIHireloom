import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from FOIHireloom.config.settings import Settings
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

from .job_tools import JOB_SEARCH_SERVICE, JobTools

INSTRUCTIONS = (
    "Search job advertisements from the Croatian Employment Service (HZZ). "
    "Jobs come from HZZ county RSS feeds, which this server imports regularly; "
    "the tools read the stored copy and never contact HZZ. Use list_regions and "
    "list_categories for valid filter values. Send users to canonical_url to "
    "read the full advertisement or apply."
)

type JobSearchServiceOpener = Callable[[], AbstractAsyncContextManager[JobSearchServiceInterface]]


class McpServer:
    """FastMCP server whose tools share one search service while it runs.

    The service, and its database engine, opens when the server starts and
    closes when it stops. Pass job_search_service to supply another one, for
    example in tests.
    """

    def __init__(self, job_search_service: JobSearchServiceOpener | None = None) -> None:
        self._job_search_service = job_search_service or DependencyService(Settings()).job_search_service
        # Unexpected errors reach the client without details; tools raise ToolError for the rest.
        self.server = FastMCP("FOIHireloom", instructions=INSTRUCTIONS, lifespan=self._lifespan,
                              mask_error_details=True)
        for group in (JobTools(),):
            group.register(self.server)

    @asynccontextmanager
    async def _lifespan(self, server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with self._job_search_service() as service:
            yield {JOB_SEARCH_SERVICE: service}

    def run(self) -> None:
        print("Starting MCP server", file=sys.stderr)
        self.server.run()
