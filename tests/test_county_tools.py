from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastmcp import Client
from fastmcp.exceptions import ToolError

from test_county_indicators import CountyDataTestCase

from FOIHireloom.api.mcp_server import INSTRUCTIONS, McpServer
from FOIHireloom.config.settings import Settings
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.services import (
    CountyIndicatorServiceInterface,
    CroatianCountyCatalog,
    JobSearchService,
    JobSearchServiceInterface,
)


class CountyToolsTests(CountyDataTestCase):
    """compare_counties and unemployment_history end to end, over the data of the service tests."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.server = McpServer(Settings(_env_file=None), job_search_service=self.open_search,
                                county_indicator_service=self.open_indicators).server

    @asynccontextmanager
    async def open_search(self) -> AsyncIterator[JobSearchServiceInterface]:
        yield JobSearchService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)), CroatianCountyCatalog())

    @asynccontextmanager
    async def open_indicators(self) -> AsyncIterator[CountyIndicatorServiceInterface]:
        yield self.service

    async def test_tools_are_read_only_and_their_schemas_bound_the_arguments(self) -> None:
        async with Client(self.server) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            for name, arguments in (
                ("compare_counties", {"counties": ["varazdinska"]}),
                ("compare_counties", {"counties": ["varazdinska"] * 7}),
                ("compare_counties", {"counties": ["varazdinska", "medimurska"], "period": "2026-9"}),
                ("compare_counties", {"counties": ["varazdinska", "medimurska"], "contract": "temporary"}),
                ("unemployment_history", {"counties": []}),
                ("unemployment_history", {"counties": ["varazdinska"], "months": 11}),
                ("unemployment_history", {"counties": ["varazdinska"], "months": 25}),
                ("unemployment_history", {"counties": ["varazdinska"], "sex": "all"}),
            ):
                with self.subTest(name=name, arguments=arguments), self.assertRaises(ToolError):
                    await client.call_tool(name, arguments)
        for name in ("compare_counties", "unemployment_history"):
            tool = tools[name]
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.openWorldHint)
            self.assertIsNotNone(tool.outputSchema)
            self.assertNotIn("ctx", tool.inputSchema["properties"])
            self.assertIn(name, INSTRUCTIONS)
        # The job filters are the same arguments as job_market_stats takes, county and top aside.
        comparison = tools["compare_counties"].inputSchema["properties"]
        market = tools["job_market_stats"].inputSchema["properties"]
        self.assertEqual({key: comparison[key] for key in set(market) - {"county", "top", "include_expired", "query"}},
                         {key: market[key] for key in set(market) - {"county", "top", "include_expired", "query"}})
        self.assertEqual(set(comparison), set(market) - {"county", "top"} | {"counties", "period"})

    async def test_compare_counties_over_mcp(self) -> None:
        await self.add_dzs()
        async with Client(self.server) as client:
            result = (await client.call_tool("compare_counties", {
                "counties": ["varazdinska", "Međimurska županija"], "query": "kuhar", "contract": "permanent",
            })).structured_content
            september = (await client.call_tool("compare_counties", {
                "counties": ["varazdinska", "medimurska"], "period": "2026-09"})).structured_content
            with self.assertRaisesRegex(ToolError, "Unknown county: Atlantida. Use county codes or names from "
                                                   "list_regions: istarska, medimurska, varazdinska"):
                await client.call_tool("compare_counties", {"counties": ["varazdinska", "Atlantida"]})
            with self.assertRaisesRegex(ToolError, "given more than once: varazdinska"):
                await client.call_tool("compare_counties", {"counties": ["varazdinska", "Varaždinska županija"]})
            with self.assertRaisesRegex(ToolError, "The place contains no words"):
                await client.call_tool("compare_counties", {"counties": ["varazdinska", "medimurska"], "place": "--"})
        self.assertEqual(set(result), {"counties", "today", "window_days", "filters", "active_filters",
                                       "requested_period", "dzs_periods", "hzz_coverage", "dzs", "sources", "notes"})
        self.assertEqual(result["active_filters"], [{"argument": "contract", "label": "na neodređeno"}])
        self.assertEqual((result["filters"]["query"], result["filters"]["contract"]), ("kuhar", "permanent"))
        vz = result["counties"][0]
        self.assertEqual(set(vz), {"code", "name", "iso_code", "hzz_data_status", "hzz_last_success_at",
                                   "filtered_jobs", "all_active_jobs", "unemployed", "active_population",
                                   "unemployment_rate", "unemployed_per_worker", "jobs_per_1000_active"})
        self.assertEqual(vz["filtered_jobs"]["jobs"], 1)
        self.assertEqual(vz["all_active_jobs"]["workers_needed_coverage"], {"part": 2, "whole": 3, "percent": 66.7})
        # Decimals arrive as JSON numbers.
        self.assertEqual(vz["unemployed_per_worker"], {"value": 360.0, "numerator": 1800, "denominator": 5,
                                                       "dzs_period": "2026-08-01", "is_provisional": False,
                                                       "unavailable_reason": None})
        self.assertEqual((vz["unemployment_rate"]["value"], vz["unemployed"]["value"]), (2.5, 1800))
        # Persons are whole numbers, as DZS counts them.
        self.assertIsInstance(vz["unemployed"]["value"], int)
        self.assertEqual(result["counties"][1]["unemployed_per_worker"]["unavailable_reason"], "no_known_workers")
        self.assertEqual(september["requested_period"], "2026-09-01")
        self.assertEqual(september["counties"][1]["unemployed"]["unavailable_reason"], "dzs_value_missing")

    async def test_unemployment_history_over_mcp(self) -> None:
        await self.add_dzs()
        async with Client(self.server) as client:
            history = (await client.call_tool("unemployment_history", {
                "counties": ["varazdinska"], "months": 24})).structured_content
            with self.assertRaisesRegex(ToolError, "Unknown county: Atlantida"):
                await client.call_tool("unemployment_history", {"counties": ["Atlantida"]})
        self.assertEqual((history["first_period"], history["last_period"], history["sex"], history["months"]),
                         ("2024-10-01", "2026-09-01", "total", 24))
        county = history["counties"][0]
        self.assertEqual(len(county["series"]), 24)
        self.assertEqual(county["series"][-1], {"period": "2026-09-01", "rate": 2.3, "is_provisional": True,
                                                "unavailable_reason": None, "missing_reason": None})
        self.assertEqual((county["change_pp"], county["same_month_previous_year"]["period"]), (-0.6, "2025-09-01"))
        self.assertIn("not a seasonal adjustment", " ".join(history["notes"]))
        self.assertEqual([file["role"] for file in history["dzs"]["files"]], ["t1", "workbook"])
