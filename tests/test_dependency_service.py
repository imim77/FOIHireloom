import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import UnemploymentHistoryRequestDTO
from FOIHireloom.dto.job_search import CategoryDTO
from FOIHireloom.services.dependency import DependencyService

COUNTY = CountyDTO(id=1, code="istarska", name="Istarska županija", iso_code="HR-18")


class DependencyServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.events = []
        self.contexts = []

        @asynccontextmanager
        async def open_work():
            work = SimpleNamespace(
                transaction_time=AsyncMock(return_value=datetime(2026, 11, 4, 12, tzinfo=UTC)),
                jobs=SimpleNamespace(list_categories=AsyncMock(return_value=[CategoryDTO(name="Kuhari", open_jobs=2)])),
                counties=SimpleNamespace(list_all=AsyncMock(return_value=[COUNTY])),
                dzs_imports=SimpleNamespace(get_latest_succeeded=AsyncMock(return_value=None)),
            )
            self.contexts.append(work)
            # Overlap contexts to prove services do not share a transaction.
            await asyncio.sleep(0)
            try:
                yield work
            finally:
                self.events.append("transaction-closed")

        @asynccontextmanager
        async def open_database():
            self.events.append("database-opened")
            try:
                yield open_work
            finally:
                self.events.append("database-closed")

        self.dependencies = DependencyService(Settings(_env_file=None), unit_of_work=open_database)

    async def test_default_read_services_share_one_pool_and_use_independent_transactions(self) -> None:
        async with self.dependencies.read_services() as (search, indicators):
            categories, history = await asyncio.gather(search.list_categories(), indicators.unemployment_history(
                UnemploymentHistoryRequestDTO(counties=(COUNTY.code,))))
            self.assertEqual(categories, (CategoryDTO(name="Kuhari", open_jobs=2),))
            self.assertEqual(history.unavailable_reason, "no_dzs_data")
            self.assertEqual(history.counties[0].series, ())
            self.assertEqual(self.events.count("database-opened"), 1)
            self.assertNotIn("database-closed", self.events)
            self.assertIsNot(self.contexts[0], self.contexts[1])
        self.assertEqual(self.events.count("database-closed"), 1)
        self.assertEqual(self.events.count("transaction-closed"), 2)

    async def test_full_overrides_skip_default_infrastructure_and_close_in_reverse_order(self) -> None:
        @asynccontextmanager
        async def search():
            self.events.append("search-opened")
            try:
                yield "search"
            finally:
                self.events.append("search-closed")

        @asynccontextmanager
        async def indicators():
            self.events.append("indicators-opened")
            try:
                yield "indicators"
            finally:
                self.events.append("indicators-closed")

        async with self.dependencies.read_services(job_search=search, county_indicators=indicators) as services:
            self.assertEqual(services, ("search", "indicators"))
        self.assertEqual(self.events, ["search-opened", "indicators-opened", "indicators-closed", "search-closed"])

    async def test_partial_override_closes_before_the_default_pool(self) -> None:
        @asynccontextmanager
        async def search():
            try:
                yield "search"
            finally:
                self.events.append("search-closed")

        async with self.dependencies.read_services(job_search=search) as (service, _):
            self.assertEqual(service, "search")
        self.assertEqual(self.events, ["database-opened", "search-closed", "database-closed"])

    async def test_second_override_failure_closes_the_first_service(self) -> None:
        @asynccontextmanager
        async def search():
            try:
                yield "search"
            finally:
                self.events.append("search-closed")

        @asynccontextmanager
        async def broken_indicators():
            raise RuntimeError("startup failed")
            yield  # This opener fails before yielding a service.

        with self.assertRaisesRegex(RuntimeError, "startup failed"):
            async with self.dependencies.read_services(job_search=search, county_indicators=broken_indicators):
                self.fail("Startup should not complete")
        self.assertEqual(self.events, ["search-closed"])

    async def test_factory_failure_closes_the_default_pool(self) -> None:
        with patch("FOIHireloom.services.dependency.CountyIndicatorServiceFactory.create",
                   side_effect=RuntimeError("assembly failed")), self.assertRaisesRegex(RuntimeError, "assembly failed"):
            async with self.dependencies.read_services():
                self.fail("Startup should not complete")
        self.assertEqual(self.events, ["database-opened", "database-closed"])
