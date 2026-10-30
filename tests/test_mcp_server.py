import unittest
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from fastmcp import Client
from fastmcp.exceptions import ToolError

from FOIHireloom.api.mcp_server import McpServer
from FOIHireloom.dto.job_search import (
    CategoryDTO,
    CoverageDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    JobSummaryDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError, PersistenceError
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

SEEN = datetime(2026, 10, 29, 3, 31, tzinfo=UTC)
SUMMARY = dict(id=7, source_job_id="1", title="KUHAR/KUHARICA", category="UGOSTITELJI, RADNICI U TURIZMU", location_text="BJELOVAR",
               municipality="BJELOVAR", published_on=date(2026, 10, 27), deadline_on=None, deadline_passed=None,
               canonical_url="https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1", quality_flags=(),
               last_seen_at=SEEN)
COVERAGE = CoverageDTO(data_status="stale", data_as_of=SEEN, stale_after_hours=6, affected_regions=(),
                       warning="Job data for the requested county was not updated in the last 6 hours.")


class FakeJobSearchService(JobSearchServiceInterface):
    def __init__(self) -> None:
        self.filters: list[JobSearchFiltersDTO] = []
        self.error: Exception | None = None

    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        self.filters.append(filters)
        self.raise_error()
        return JobSearchPageDTO(jobs=(JobSummaryDTO(**SUMMARY),), next_cursor="next", coverage=COVERAGE)

    async def get_job(self, job_id: int) -> JobDetailsDTO:
        self.raise_error()
        return JobDetailsDTO(**SUMMARY | {"id": job_id}, description_text="Rad u kuhinji.",
                             availability_status="unknown", first_seen_at=SEEN, content_changed_at=SEEN)

    async def list_regions(self) -> tuple[RegionDTO, ...]:
        self.raise_error()
        return (RegionDTO(code="grad-zagreb", name="Grad Zagreb", open_jobs=3, data_status="fresh", last_success_at=SEEN),)

    async def list_categories(self) -> tuple[CategoryDTO, ...]:
        self.raise_error()
        return (CategoryDTO(name="UGOSTITELJI, RADNICI U TURIZMU", open_jobs=2),)

    def raise_error(self) -> None:
        if self.error is not None:
            raise self.error


class McpServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = FakeJobSearchService()
        self.open_services = 0
        self.server = McpServer(self.open_service).server

    @asynccontextmanager
    async def open_service(self) -> AsyncIterator[JobSearchServiceInterface]:
        self.open_services += 1
        try:
            yield self.service
        finally:
            self.open_services -= 1

    async def test_server_registers_read_only_job_tools(self) -> None:
        async with Client(self.server) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            self.assertEqual(self.open_services, 1)
        self.assertEqual(self.open_services, 0)
        self.assertEqual(set(tools), {"search_jobs", "get_job", "list_regions", "list_categories"})
        for tool in tools.values():
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.openWorldHint)
                self.assertTrue(tool.description)
                self.assertIsNotNone(tool.outputSchema)
        self.assertNotIn("ctx", tools["search_jobs"].inputSchema["properties"])
        self.assertEqual(tools["search_jobs"].inputSchema["properties"]["limit"]["maximum"], 20)

    async def test_search_jobs_passes_filters_and_returns_structured_page(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("search_jobs", {"query": "kuhar", "county": "Grad Zagreb", "limit": 5})
        self.assertEqual(self.service.filters, [JobSearchFiltersDTO(query="kuhar", county="Grad Zagreb", limit=5)])
        page = result.structured_content
        self.assertEqual(page["next_cursor"], "next")
        self.assertEqual(page["jobs"][0]["published_on"], "2026-10-27")
        self.assertIsNone(page["jobs"][0]["deadline_passed"])
        self.assertEqual(page["jobs"][0]["display_title"], "KUHAR/KUHARICA")
        self.assertEqual((page["coverage"]["data_status"], page["coverage"]["warning"]),
                         ("stale", COVERAGE.warning))

    async def test_other_tools_return_service_results(self) -> None:
        async with Client(self.server) as client:
            job = (await client.call_tool("get_job", {"job_id": 42})).structured_content
            regions = (await client.call_tool("list_regions", {})).structured_content
            categories = (await client.call_tool("list_categories", {})).structured_content
        self.assertEqual((job["id"], job["description_text"], job["listings"]), (42, "Rad u kuhinji.", []))
        self.assertEqual(regions["result"], [{"code": "grad-zagreb", "name": "Grad Zagreb", "open_jobs": 3,
                                              "data_status": "fresh", "last_success_at": "2026-10-29T03:31:00Z"}])
        self.assertEqual(categories["result"][0]["open_jobs"], 2)

    async def test_invalid_arguments_are_rejected_before_the_service(self) -> None:
        async with Client(self.server) as client:
            for tool, arguments in (("search_jobs", {"limit": 21}), ("search_jobs", {"query": "x" * 201}),
                                    ("get_job", {"job_id": 0}), ("get_job", {})):
                with self.subTest(tool=tool, arguments=arguments), self.assertRaises(ToolError):
                    await client.call_tool(tool, arguments)
        self.assertEqual(self.service.filters, [])

    async def test_errors_the_caller_can_act_on_keep_their_message(self) -> None:
        cases = {
            NotFoundError("county", "Atlantida"): "County Atlantida not found.",
            InvalidJobSearchError("The cursor is not valid."): "The cursor is not valid.",
            PersistenceError("connection to 10.0.0.5 refused"): "Job data is temporarily unavailable",
        }
        async with Client(self.server) as client:
            for error, message in cases.items():
                self.service.error = error
                with self.subTest(error=error), self.assertRaisesRegex(ToolError, message) as raised:
                    await client.call_tool("search_jobs", {})
                self.assertNotIn("10.0.0.5", str(raised.exception))

    async def test_unexpected_errors_are_masked(self) -> None:
        self.service.error = RuntimeError("secret internal detail")
        async with Client(self.server) as client:
            with self.assertRaises(ToolError) as raised:
                await client.call_tool("list_regions", {})
        self.assertNotIn("secret", str(raised.exception))
