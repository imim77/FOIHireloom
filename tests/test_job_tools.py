from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from uuid import uuid4

from fastmcp import Client
from fastmcp.exceptions import ToolError

from model_test_case import ModelTestCase

from FOIHireloom.api.mcp_server import McpServer
from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.services import CroatianCountyCatalog, JobSearchService, JobSearchServiceInterface


class JobToolsDatabaseTests(ModelTestCase):
    """The tools end to end over a migrated database."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        county = County(code="grad-zagreb", name="Grad Zagreb")
        self.session.add(county)
        await self.session.flush()
        feed = SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label="ZG", scope="county",
                          feed_url="http://burzarada.hzz.hr/rss/rsszup21.xml")
        self.session.add(feed)
        await self.session.flush()
        self.job_ids = []
        for number in range(3):
            job = Job(provider="hzz", source_job_id=str(number), canonical_url=f"https://example.com/{number}",
                      content_hash=str(number), title=f"ČISTAČICA {number}", description_text="Čišćenje ureda.",
                      published_on=date(2026, 10, 20 + number))
            self.session.add(job)
            await self.session.flush()
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feed.id))
            self.job_ids.append(job.id)
        await self.session.commit()
        self.server = McpServer(self.open_service).server

    @asynccontextmanager
    async def open_service(self) -> AsyncIterator[JobSearchServiceInterface]:
        yield JobSearchService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)), CroatianCountyCatalog())

    async def test_search_pages_and_details_over_mcp(self) -> None:
        async with Client(self.server) as client:
            first = (await client.call_tool("search_jobs", {"query": "cistacica", "county": "Grad Zagreb",
                                                            "limit": 2})).structured_content
            second = (await client.call_tool("search_jobs", {"query": "cistacica", "county": "Grad Zagreb",
                                                             "limit": 2, "cursor": first["next_cursor"]})).structured_content
            job = (await client.call_tool("get_job", {"job_id": self.job_ids[0]})).structured_content
            regions = (await client.call_tool("list_regions", {})).structured_content["result"]
            with self.assertRaisesRegex(ToolError, "County Atlantida not found"):
                await client.call_tool("search_jobs", {"county": "Atlantida"})
            with self.assertRaisesRegex(ToolError, "Job .* not found"):
                await client.call_tool("get_job", {"job_id": max(self.job_ids) + 1})
        self.assertEqual([job["id"] for job in first["jobs"] + second["jobs"]], self.job_ids[::-1])
        self.assertIsNone(second["next_cursor"])
        # The feed has never been loaded successfully, which the result must say.
        self.assertEqual(first["coverage"]["data_status"], "unavailable")
        self.assertIn("Grad Zagreb (never loaded)", first["coverage"]["warning"])
        self.assertEqual((job["title"], job["description_text"]), ("ČISTAČICA 0", "Čišćenje ureda."))
        self.assertEqual(job["listings"][0]["county_code"], "grad-zagreb")
        self.assertEqual(regions, [{"code": "grad-zagreb", "name": "Grad Zagreb", "open_jobs": 3,
                                    "data_status": "unavailable", "last_success_at": None}])
