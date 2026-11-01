import asyncio
import logging
import os
import socket
import unittest
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, suppress
from datetime import UTC, date, datetime
from unittest import mock

import httpx
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from FOIHireloom.api.apps.views import JOB_CARDS, JOBS_BY_COUNTY
from FOIHireloom.api.mcp_server import McpServer
from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.job_comparison import (
    ComparedJobDTO,
    ComparisonCellDTO,
    ComparisonRowDTO,
    JobComparisonConditionsDTO,
    JobComparisonDTO,
)
from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO
from FOIHireloom.dto.job_search import (
    CategoryDTO,
    CoverageDTO,
    JobCardDTO,
    JobCardsPageDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    JobSummaryDTO,
    RegionDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError, PersistenceError
from FOIHireloom.main import settings_from_args
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface

SETTINGS = Settings(_env_file=None)
SEEN = datetime(2026, 10, 29, 3, 31, tzinfo=UTC)
SUMMARY = dict(id=7, source_job_id="1", title="KUHAR/KUHARICA", category="UGOSTITELJI, RADNICI U TURIZMU", location_text="BJELOVAR",
               municipality="BJELOVAR", published_on=date(2026, 10, 27), deadline_on=None, deadline_passed=None,
               canonical_url="https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1", quality_flags=(),
               last_seen_at=SEEN)
COVERAGE = CoverageDTO(data_status="stale", data_as_of=SEEN, stale_after_hours=6, affected_regions=(),
                       warning="Job data for the requested county was not updated in the last 6 hours.")
NO_BREAKDOWNS = dict.fromkeys(("categories", "employers", "contracts", "employment_tags", "working_time",
                               "experience_bands", "education_levels", "accommodation", "schedule_tags",
                               "transport_allowance"), ())


class FakeJobSearchService(JobSearchServiceInterface):
    def __init__(self) -> None:
        self.filters: list[JobSearchFiltersDTO] = []
        self.market_filters: list[JobMarketFiltersDTO] = []
        self.comparisons: list[tuple[list[int], JobComparisonConditionsDTO | None]] = []
        self.error: Exception | None = None

    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        self.filters.append(filters)
        self.raise_error()
        return JobSearchPageDTO(jobs=(JobSummaryDTO(**SUMMARY),), next_cursor="next", coverage=COVERAGE)

    async def search_cards(self, filters: JobSearchFiltersDTO) -> JobCardsPageDTO:
        self.filters.append(filters)
        self.raise_error()
        return JobCardsPageDTO(jobs=(JobCardDTO(**SUMMARY, workers_needed=2, employment_type="Na neodređeno"),),
                               next_cursor="next", coverage=COVERAGE, today=SEEN.date(),
                               unknown_conditions={"full_time": 1} if filters.full_time is not None else {},
                               unknown_total=int(filters.full_time is not None))

    async def market_stats(self, filters: JobMarketFiltersDTO) -> JobMarketStatsDTO:
        self.market_filters.append(filters)
        self.raise_error()
        return JobMarketStatsDTO(jobs=0, with_details=0, with_category=0, category_from_description=0,
                                 category_from_feed=0, workers_needed=0, published_recently=0, closing_soon=0,
                                 counties=(), **NO_BREAKDOWNS, today=SEEN.date(), coverage=COVERAGE)

    async def get_job(self, job_id: int) -> JobDetailsDTO:
        self.raise_error()
        return JobDetailsDTO(**SUMMARY | {"id": job_id}, description_text="Rad u kuhinji.",
                             availability_status="unknown", first_seen_at=SEEN, content_changed_at=SEEN)

    async def compare_jobs(
        self, job_ids: Sequence[int], conditions: JobComparisonConditionsDTO | None = None,
    ) -> JobComparisonDTO:
        self.comparisons.append((list(job_ids), conditions))
        self.raise_error()
        experience = (conditions or JobComparisonConditionsDTO()).max_experience_months
        return JobComparisonDTO(
            today=SEEN.date(),
            jobs=tuple(ComparedJobDTO(id=job_id, display_title="KUHAR/KUHARICA", employer_name=None,
                                      county_name="Grad Zagreb", display_location="ZAGREB",
                                      canonical_url=SUMMARY["canonical_url"], details_status="pending", category=None,
                                      category_source=None, conditions=None) for job_id in job_ids),
            rows=(ComparisonRowDTO(aspect="experience", differs=False, condition=experience, cells=tuple(
                ComparisonCellDTO(job_id=job_id, value=None, evidence=None,
                                  verdict=None if experience is None else "unknown",
                                  reason=None if experience is None else "the job's HZZ page has not been read yet")
                for job_id in job_ids)),),
            conditions=conditions,
        )

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
        self.server = McpServer(SETTINGS, job_search_service=self.open_service).server

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
        self.assertEqual(set(tools), {"search_jobs", "show_jobs", "job_market_stats", "show_jobs_by_county", "get_job",
                                      "compare_jobs", "list_regions", "list_categories"})
        for tool in tools.values():
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.openWorldHint)
                self.assertTrue(tool.description)
                self.assertIsNotNone(tool.outputSchema)
        self.assertNotIn("ctx", tools["search_jobs"].inputSchema["properties"])
        self.assertEqual(tools["search_jobs"].inputSchema["properties"]["limit"]["maximum"], 20)
        self.assertEqual(tools["job_market_stats"].inputSchema["properties"]["top"]["maximum"], 50)
        # A plain tool for now: no MCP App view.
        self.assertNotIn("ui", tools["compare_jobs"].meta or {})

    async def test_compare_jobs_takes_two_or_three_ids_and_the_users_conditions(self) -> None:
        async with Client(self.server) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == "compare_jobs")
        schema = tool.inputSchema
        self.assertEqual(schema["required"], ["job_ids"])
        self.assertEqual(set(schema["properties"]), {"job_ids", "max_experience_months", "contract", "full_time",
                                                     "education", "accommodation"})
        job_ids = schema["properties"]["job_ids"]
        self.assertEqual((job_ids["type"], job_ids["minItems"], job_ids["maxItems"], job_ids["items"]["minimum"]),
                         ("array", 2, 3, 1))
        enums = {name: next(option["enum"] for option in schema["properties"][name]["anyOf"] if "enum" in option)
                 for name in ("contract", "education")}
        self.assertEqual(enums, {"contract": ["permanent", "fixed_term", "other"],
                                 "education": ["primary_lower", "primary", "secondary_3", "secondary_4", "college",
                                               "university"]})
        experience = schema["properties"]["max_experience_months"]
        self.assertEqual((experience["anyOf"][0]["minimum"], experience["anyOf"][0]["maximum"]), (0, 600))
        # The conditions describe the user, not a filter on the jobs.
        self.assertTrue(experience["description"].startswith("The user's experience in months"))
        self.assertIn("the user needs accommodation", schema["properties"]["accommodation"]["description"])
        self.assertIn("never that the employer will accept the user", " ".join(tool.description.split()))
        self.assertTrue(tool.annotations.readOnlyHint and tool.annotations.idempotentHint)

    async def test_compare_jobs_passes_ids_in_order_and_the_conditions(self) -> None:
        conditions = {"max_experience_months": 0, "contract": "permanent", "full_time": True,
                      "education": "secondary_4", "accommodation": True}
        async with Client(self.server) as client:
            compared = (await client.call_tool("compare_jobs", {"job_ids": [9, 7, 8]} | conditions)).structured_content
            plain = (await client.call_tool("compare_jobs", {"job_ids": [8, 7]})).structured_content
            # Leaving out conditions and passing them as null are the same: no conditions.
            nulls = dict.fromkeys(conditions)
            await client.call_tool("compare_jobs", {"job_ids": [7, 8]} | nulls)
        self.assertEqual(self.service.comparisons, [([9, 7, 8], JobComparisonConditionsDTO(**conditions)),
                                                    ([8, 7], None), ([7, 8], None)])
        self.assertEqual([job["id"] for job in compared["jobs"]], [9, 7, 8])
        self.assertEqual((compared["today"], compared["conditions"]), ("2026-10-29", conditions))
        row = compared["rows"][0]
        self.assertEqual((row["aspect"], row["condition"], [cell["verdict"] for cell in row["cells"]]),
                         ("experience", 0, ["unknown"] * 3))
        self.assertEqual((plain["conditions"], plain["rows"][0]["cells"][0]["verdict"]), (None, None))

    async def test_compare_jobs_rejects_wrong_counts_before_the_service_and_keeps_its_errors(self) -> None:
        async with Client(self.server) as client:
            # Fewer than two, more than three and impossible ids fail on the input schema.
            for arguments in ({"job_ids": [7]}, {"job_ids": [7, 8, 9, 10]}, {"job_ids": []}, {"job_ids": [7, 0]},
                              {}, {"job_ids": [7, 8], "contract": "temporary"},
                              {"job_ids": [7, 8], "max_experience_months": -1}):
                with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                    await client.call_tool("compare_jobs", arguments)
            self.assertEqual(self.service.comparisons, [])
            # Repeated and missing ids are the service's to reject.
            for error, message in (
                (InvalidJobSearchError("Choose different jobs to compare; given more than once: 7."),
                 "Choose different jobs to compare; given more than once: 7."),
                (NotFoundError("job", "99"), "Job 99 not found."),
                (PersistenceError("connection to 10.0.0.5 refused"), "Job data is temporarily unavailable"),
            ):
                self.service.error = error
                with self.subTest(error=error), self.assertRaisesRegex(ToolError, message) as raised:
                    await client.call_tool("compare_jobs", {"job_ids": [7, 99]})
                self.assertNotIn("10.0.0.5", str(raised.exception))

    async def test_search_jobs_passes_filters_and_returns_structured_page(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("search_jobs", {"query": "kuhar", "county": "Grad Zagreb", "limit": 5})
        self.assertEqual(self.service.filters, [JobSearchFiltersDTO(query="kuhar", county="Grad Zagreb", limit=5)])
        page = result.structured_content
        self.assertEqual(page["next_cursor"], "next")
        self.assertEqual(page["jobs"][0]["published_on"], "2026-10-27")
        self.assertIsNone(page["jobs"][0]["deadline_passed"])
        self.assertEqual(page["jobs"][0]["display_title"], "KUHAR/KUHARICA")
        self.assertEqual(page["jobs"][0]["display_location"], "BJELOVAR")
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

    async def test_jobs_by_county_is_an_mcp_app_served_from_the_built_page(self) -> None:
        async with Client(self.server) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == "show_jobs_by_county")
            uri = tool.meta["ui"]["resourceUri"]
            resources = {str(resource.uri): resource for resource in await client.list_resources()}
            chart_page = (await client.read_resource(uri))[0]
            chart = (await client.call_tool("show_jobs_by_county", {"query": "kuhar", "top": 3})).structured_content
            by_workers = (await client.call_tool("show_jobs_by_county", {"metric": "workers_needed"})).structured_content
        self.assertRegex(uri, r"^ui://foihireloom/jobs-by-county-[0-9a-f]{12}\.html$")
        self.assertEqual(resources[uri].mimeType, "text/html;profile=mcp-app")
        self.assertEqual(chart_page.text, JOBS_BY_COUNTY.page())
        self.assertEqual(self.service.market_filters, [JobMarketFiltersDTO(query="kuhar"), JobMarketFiltersDTO()])
        self.assertEqual((chart["title"], chart["top"], chart["counties"], chart["coverage"]["warning"]),
                         ("Broj oglasa po županijama", 3, [], COVERAGE.warning))
        self.assertEqual((by_workers["metric"], by_workers["title"]),
                         ("workers_needed", "Broj traženih radnika po županijama"))

    async def test_show_jobs_is_an_mcp_app_whose_cards_carry_the_job_page_values(self) -> None:
        async with Client(self.server) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == "show_jobs")
            uri = tool.meta["ui"]["resourceUri"]
            resources = {str(resource.uri): resource for resource in await client.list_resources()}
            cards_page = (await client.read_resource(uri))[0]
            cards = (await client.call_tool("show_jobs", {"query": "kuhar", "county": "istarska",
                                                          "cursor": "abc"})).structured_content
        self.assertRegex(uri, r"^ui://foihireloom/job-cards-[0-9a-f]{12}\.html$")
        self.assertEqual(resources[uri].mimeType, "text/html;profile=mcp-app")
        self.assertEqual(cards_page.text, JOB_CARDS.page())
        self.assertEqual(self.service.filters,
                         [JobSearchFiltersDTO(query="kuhar", county="istarska", limit=6, cursor="abc")])
        self.assertEqual((cards["title"], cards["description"], cards["next_cursor"], cards["today"]),
                         ("Oglasi za „kuhar”", "Aktivni oglasi na dan 29. 10. 2026.", "next", "2026-10-29"))
        self.assertEqual(cards["active_filters"], [{"argument": "county", "label": "Istarska županija"}])
        self.assertEqual((cards["filters"]["query"], cards["filters"]["limit"], cards["filters"]["cursor"]),
                         ("kuhar", 6, None))
        job = cards["jobs"][0]
        self.assertEqual((job["display_title"], job["workers_needed"], job["employment_type"], job["education"]),
                         ("KUHAR/KUHARICA", 2, "Na neodređeno", None))
        self.assertEqual(cards["coverage"]["warning"], COVERAGE.warning)

    async def test_condition_filters_reach_the_service_and_the_cards_keep_them_for_the_next_page(self) -> None:
        conditions = {"max_experience_months": 0, "contract": "permanent", "full_time": True,
                      "education": "secondary_4", "accommodation": False,
                      "employment_tags": ["new_position", "retirees"], "place": "Varaždin"}
        async with Client(self.server) as client:
            await client.call_tool("search_jobs", conditions)
            cards = (await client.call_tool("show_jobs", conditions | {"cursor": "abc"})).structured_content
            # The cards view asks for more with the filters it was given and next_cursor.
            await client.call_tool("show_jobs", cards["filters"] | {"cursor": cards["next_cursor"]})
            await client.call_tool("job_market_stats", conditions)
            await client.call_tool("show_jobs_by_county", conditions)
        self.assertEqual(self.service.filters, [JobSearchFiltersDTO(**conditions),
                                                JobSearchFiltersDTO(**conditions, limit=6, cursor="abc"),
                                                JobSearchFiltersDTO(**conditions, limit=6, cursor="next")])
        self.assertEqual(self.service.market_filters, [JobMarketFiltersDTO(**conditions)] * 2)
        self.assertEqual({name: cards["filters"][name] for name in conditions}, conditions)
        self.assertEqual((cards["unknown_conditions"], cards["unknown_total"]), ({"full_time": 1}, 1))

    async def test_job_market_stats_passes_filters_and_returns_coverage(self) -> None:
        async with Client(self.server) as client:
            stats = (await client.call_tool("job_market_stats", {"query": "kuhar", "county": "istarska",
                                                                 "top": 3})).structured_content
        self.assertEqual(self.service.market_filters, [JobMarketFiltersDTO(query="kuhar", county="istarska", top=3)])
        self.assertEqual((stats["jobs"], stats["window_days"], stats["today"]), (0, 7, "2026-10-29"))
        self.assertEqual(stats["coverage"]["warning"], COVERAGE.warning)

    async def test_invalid_arguments_are_rejected_before_the_service(self) -> None:
        async with Client(self.server) as client:
            for tool, arguments in (("search_jobs", {"limit": 21}), ("search_jobs", {"query": "x" * 201}),
                                    ("show_jobs", {"limit": 0}), ("show_jobs", {"limit": 21}),
                                    ("job_market_stats", {"top": 0}), ("job_market_stats", {"top": 51}),
                                    ("show_jobs_by_county", {"top": 0}), ("show_jobs_by_county", {"top": 22}),
                                    ("show_jobs_by_county", {"metric": "share"}),
                                    ("search_jobs", {"contract": "temporary"}), ("search_jobs", {"place": "x" * 201}),
                                    ("show_jobs", {"education": "doctorate"}), ("show_jobs", {"full_time": "often"}),
                                    ("job_market_stats", {"employment_tags": ["remote"]}),
                                    ("job_market_stats", {"max_experience_months": 601}),
                                    ("show_jobs_by_county", {"max_experience_months": -1}),
                                    ("show_jobs_by_county", {"accommodation": "hostel"}),
                                    ("get_job", {"job_id": 0}), ("get_job", {})):
                with self.subTest(tool=tool, arguments=arguments), self.assertRaises(ToolError):
                    await client.call_tool(tool, arguments)
        self.assertEqual((self.service.filters, self.service.market_filters), ([], []))

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


class McpHttpTransportTests(unittest.IsolatedAsyncioTestCase):
    """The server over a real local socket, as an HTTP client sees it."""

    @classmethod
    def tearDownClass(cls) -> None:
        logging.getLogger("uvicorn.error").disabled = False

    async def serve(self, **settings: object) -> str:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.service = FakeJobSearchService()
        server = McpServer(Settings(_env_file=None, MCP_TRANSPORT="http", **settings),
                           job_search_service=self.open_service)
        task = asyncio.create_task(server.run_http_async(sockets=[sock]))
        self.addAsyncCleanup(self.stop, task, sock)
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        async with httpx.AsyncClient() as http:
            for _ in range(100):
                with suppress(httpx.TransportError):
                    if (await http.get(f"{base}/health")).status_code == 200:
                        # Cancelling the server makes uvicorn log the cancelled lifespan as an
                        # error when the loop closes. uvicorn configures its loggers on start,
                        # so they can only be silenced now.
                        logging.getLogger("uvicorn.error").disabled = True
                        return base
                await asyncio.sleep(0.05)
        self.fail("HTTP server did not start")

    @asynccontextmanager
    async def open_service(self) -> AsyncIterator[JobSearchServiceInterface]:
        yield self.service

    @staticmethod
    async def stop(task: asyncio.Task, sock: socket.socket) -> None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        sock.close()

    async def test_tools_and_health_are_served_over_http(self) -> None:
        base = await self.serve(MCP_PATH="/tools")
        async with Client(f"{base}/tools") as client:
            self.assertEqual(len(await client.list_tools()), 8)
            page = (await client.call_tool("search_jobs", {"query": "kuhar"})).structured_content
        self.assertEqual(page["jobs"][0]["title"], "KUHAR/KUHARICA")
        async with httpx.AsyncClient() as http:
            health = await http.get(f"{base}/health")
            missing = await http.post(f"{base}/mcp")
        self.assertEqual((health.status_code, health.json()), (200, {"status": "ok"}))
        self.assertEqual(missing.status_code, 404)

    async def test_unknown_host_headers_are_rejected_unless_allowed(self) -> None:
        base = await self.serve(MCP_ALLOWED_HOSTS=["tunnel.example"])
        async with httpx.AsyncClient() as http:
            statuses = {
                host: (await http.post(f"{base}/mcp", headers={"Host": host}, json={})).status_code
                for host in ("evil.example", "tunnel.example", "localhost")
            }
        self.assertIn(statuses["evil.example"], {403, 421})
        self.assertNotIn(statuses["tunnel.example"], {403, 421})
        self.assertNotIn(statuses["localhost"], {403, 421})


class McpSettingsTests(unittest.TestCase):
    def test_defaults_keep_stdio_and_a_local_http_address(self) -> None:
        self.assertEqual((SETTINGS.MCP_TRANSPORT, SETTINGS.MCP_HOST, SETTINGS.MCP_PORT, SETTINGS.MCP_PATH,
                          SETTINGS.MCP_ALLOWED_HOSTS), ("stdio", "127.0.0.1", 8000, "/mcp", []))

    def test_invalid_values_are_rejected(self) -> None:
        for values in ({"MCP_TRANSPORT": "sse"}, {"MCP_PORT": 0}, {"MCP_PORT": 70000}, {"MCP_PATH": "mcp"},
                       {"MCP_PATH": "/a b"}, {"MCP_HOST": ""}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Settings(_env_file=None, **values)

    def test_allowed_hosts_are_comma_separated_in_the_environment(self) -> None:
        with mock.patch.dict(os.environ, {"MCP_ALLOWED_HOSTS": "a.ngrok-free.app, b.example.com,"}):
            self.assertEqual(Settings(_env_file=None).MCP_ALLOWED_HOSTS, ["a.ngrok-free.app", "b.example.com"])

    def test_command_line_options_override_settings(self) -> None:
        with mock.patch.dict(os.environ, {"MCP_TRANSPORT": "stdio", "MCP_PORT": "9000"}):
            settings = settings_from_args(["--transport", "http", "--host", "0.0.0.0", "--path", "/x"])
        self.assertEqual((settings.MCP_TRANSPORT, settings.MCP_HOST, settings.MCP_PORT, settings.MCP_PATH),
                         ("http", "0.0.0.0", 9000, "/x"))
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            settings_from_args(["--transport", "sse"])

    def test_run_picks_the_configured_transport(self) -> None:
        for settings, expected in (
            (SETTINGS, mock.call("stdio")),
            (Settings(_env_file=None, MCP_TRANSPORT="http", MCP_PORT=9001, MCP_ALLOWED_HOSTS=["t.example"]),
             mock.call("http", host="127.0.0.1", port=9001, path="/mcp", host_origin_protection="auto",
                       allowed_hosts=["t.example"])),
        ):
            server = McpServer(settings, job_search_service=FakeOpener())
            with self.subTest(transport=settings.MCP_TRANSPORT), \
                    mock.patch.object(server.server, "run") as run, mock.patch("sys.stderr"):
                server.run()
            self.assertEqual(run.call_args, expected)


class FakeOpener:
    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[JobSearchServiceInterface]:
        yield FakeJobSearchService()
