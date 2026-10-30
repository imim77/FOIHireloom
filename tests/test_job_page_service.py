from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select, update

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.integrations.concrete.hzz_job_page import HzzJobPageClient
from FOIHireloom.services import HzzJobPageParser, JobPageService

FIXTURES = Path(__file__).parent / "fixtures"


class JobPageServiceTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        county = County(code="istarska", name="Istarska županija")
        self.session.add(county)
        await self.session.flush()
        feed = SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label="IS", scope="county",
                          feed_url="http://burzarada.hzz.hr/rss/rsszup18.xml")
        self.session.add(feed)
        await self.session.flush()
        self.ids = {}
        for number, web_sifra in enumerate(("101", "102", "103", "104")):
            job = Job(provider="hzz", source_job_id=web_sifra, content_hash=f"hash-{web_sifra}",
                      canonical_url=f"https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra={web_sifra}",
                      published_on=date(2026, 10, 20 + number))
            self.session.add(job)
            await self.session.flush()
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feed.id))
            self.ids[web_sifra] = job.id
        await self.session.commit()
        self.pages = {"101": "school", "102": "restaurant", "103": "school", "104": "school"}
        self.status: dict[str, int] = {}
        self.requests: list[str] = []
        self.sleeps: list[float] = []
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))
        self.addAsyncCleanup(self.http.aclose)
        self.sessions = SessionManager(self.engine)

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.assertEqual(self.engine.pool.checkedout(), 0, "Downloads must not hold a database connection")
        if request.url.path == "/ErrorPage.aspx":
            return httpx.Response(200, content=(FIXTURES / "hzz_job_page_error.html").read_bytes())
        web_sifra = request.url.params["WebSifra"]
        self.requests.append(web_sifra)
        if self.status.get(web_sifra, 200) != 200:
            return httpx.Response(self.status[web_sifra])
        if self.pages[web_sifra] == "error":
            return httpx.Response(302, headers={"Location": "/ErrorPage.aspx?errorCode=GenericError"})
        return httpx.Response(200, content=(FIXTURES / f"hzz_job_page_{self.pages[web_sifra]}.html").read_bytes())

    def service(self, **options) -> JobPageService:
        async def sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        return JobPageService(HzzJobPageClient(self.http), HzzJobPageParser(), SqlAlchemyUnitOfWorkFactory(self.sessions),
                              sleep=sleep, **options)

    async def jobs(self) -> dict[str, Job]:
        async with self.sessions.session() as reader:
            return {job.source_job_id: job for job in await reader.scalars(select(Job))}

    async def test_fetches_due_pages_newest_first_with_a_pause_between_requests(self) -> None:
        result = await self.service(delay_seconds=1.5).fetch_due(limit=3)
        self.assertEqual(self.requests, ["104", "103", "102"])
        self.assertEqual(self.sleeps, [1.5, 1.5])
        self.assertEqual(result.model_dump(), {"attempted": 3, "fetched": 3, "unavailable": 0, "failed": 0,
                                               "remaining": 1, "stopped_early": False})
        jobs = await self.jobs()
        self.assertEqual((jobs["102"].page_status, jobs["102"].page_valid_until, jobs["102"].page_work_place),
                         ("fetched", date(2026, 11, 27), "PULA-POLA, ISTARSKA ŽUPANIJA"))
        self.assertEqual((jobs["102"].page_source_hash, jobs["101"].page_status), ("hash-102", "pending"))

        # Nothing is due again until the feed content changes.
        self.requests.clear()
        await self.service().fetch_due(limit=10)
        self.assertEqual(self.requests, ["101"])
        await self.session.execute(update(Job).where(Job.id == self.ids["103"]).values(content_hash="changed"))
        await self.session.commit()
        self.requests.clear()
        result = await self.service().fetch_due(limit=10)
        self.assertEqual((self.requests, result.fetched, result.remaining), (["103"], 1, 0))

    async def test_error_pages_and_failures_are_recorded_and_keep_earlier_values(self) -> None:
        await self.service().fetch_due(limit=10)
        self.pages["104"] = "error"
        self.status["103"] = 503
        await self.session.execute(update(Job).where(Job.id.in_([self.ids["104"], self.ids["103"]]))
                                   .values(content_hash="changed"))
        await self.session.commit()
        result = await self.service().fetch_due(limit=10)
        self.assertEqual((result.unavailable, result.failed, result.fetched), (1, 1, 0))
        jobs = await self.jobs()
        self.assertEqual((jobs["104"].page_status, jobs["104"].page_valid_until), ("unavailable", date(2026, 11, 6)))
        self.assertIn("error page", jobs["104"].page_error)
        self.assertEqual((jobs["103"].page_status, jobs["103"].page_error),
                         ("failed", "HZZ job page returned HTTP 503."))
        # Retried only after retry_after has passed.
        self.assertEqual(result.remaining, 0)
        self.requests.clear()
        result = await self.service(retry_after=timedelta(microseconds=1)).fetch_due(limit=10)
        self.assertEqual(sorted(self.requests), ["103", "104"])

    async def test_stops_after_repeated_failed_downloads(self) -> None:
        self.status = {web_sifra: 500 for web_sifra in self.pages}
        result = await self.service(max_consecutive_failures=2).fetch_due(limit=10)
        self.assertEqual((result.attempted, result.failed, result.stopped_early), (2, 2, True))
        self.assertEqual(self.requests, ["104", "103"])
        self.assertEqual(result.remaining, 2)

    async def test_invalid_settings_are_rejected(self) -> None:
        for options in ({"delay_seconds": -1}, {"retry_after": timedelta(0)}, {"max_consecutive_failures": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.service(**options)
        with self.assertRaises(ValueError):
            await self.service().fetch_due(limit=0)
