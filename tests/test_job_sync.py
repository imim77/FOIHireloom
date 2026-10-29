from uuid import uuid4

import httpx
from sqlalchemy import func, select

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed, SyncRun
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.exceptions import NotFoundError
from FOIHireloom.integrations.concrete.hzz_feed import HzzFeedClient
from FOIHireloom.services import HzzFeedParser, JobSyncService


def ad(web_sifra: str, title: str = "KUHAR/KUHARICA", deadline: str = "30.11.2026") -> str:
    link = f"http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra={web_sifra}"
    description = (f"Opis posla: {title}, Kategorija: UGOSTITELJI, RADNICI U TURIZMU, Rok za prijavu: {deadline}, "
                   "Mjesto rada: BJELOVAR, Općina: BJELOVAR, Županija: BJELOVARSKO-BILOGORSKA")
    return (f"<item><title>{title}</title><subject>{title}</subject><pubDate>27.10.2026</pubDate>"
            f"<description>{description}</description><link>{link}</link><guid>{link}</guid></item>")


class JobSyncTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        county = County(code="bjelovarsko-bilogorska", name="Bjelovarsko-bilogorska županija")
        self.session.add(county)
        await self.session.flush()
        self.feeds = {}
        for number in (1, 2):
            feed = SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label=f"FEED {number}", scope="county",
                              feed_url=f"http://burzarada.hzz.hr/rss/rsszup{number}.xml")
            self.session.add(feed)
            await self.session.flush()
            self.feeds[number] = feed.id
        await self.session.commit()
        # Per feed number: list of <item> strings, HTTP status and ETag served.
        self.items = {1: [ad("1"), ad("2"), ad("3")], 2: [ad("10")]}
        self.status = {1: 200, 2: 200}
        self.etag = {1: '"v1"', 2: '"w1"'}
        self.requests: list[httpx.Request] = []
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))
        self.addAsyncCleanup(self.http.aclose)
        self.sessions = SessionManager(self.engine)
        self.service = JobSyncService(HzzFeedClient(self.http), HzzFeedParser(), SqlAlchemyUnitOfWorkFactory(self.sessions))

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.assertEqual(self.engine.pool.checkedout(), 0, "Downloads must not hold a database connection")
        number = int(request.url.path.removeprefix("/rss/rsszup").removesuffix(".xml"))
        if self.status[number] != 200:
            return httpx.Response(self.status[number])
        if request.headers.get("if-none-match") == self.etag[number]:
            return httpx.Response(304, headers={"ETag": self.etag[number]})
        body = ('<?xml version="1.0" encoding="iso-8859-2"?><rss version="2.0"><channel>'
                + "".join(self.items[number]) + "</channel></rss>").encode("iso-8859-2")
        return httpx.Response(200, content=body, headers={
            "ETag": self.etag[number], "Last-Modified": "Thu, 29 Oct 2026 03:31:10 GMT",
        })

    async def jobs(self) -> dict[str, Job]:
        async with self.sessions.session() as reader:
            return {job.source_job_id: job for job in await reader.scalars(select(Job))}

    async def memberships(self, number: int) -> dict[str, str]:
        async with self.sessions.session() as reader:
            rows = await reader.execute(
                select(Job.source_job_id, JobFeedMembership.presence_status)
                .join(Job).where(JobFeedMembership.feed_id == self.feeds[number])
            )
            return dict(rows.all())

    async def runs(self, number: int) -> list[SyncRun]:
        async with self.sessions.session() as reader:
            return list(await reader.scalars(
                select(SyncRun).where(SyncRun.feed_id == self.feeds[number]).order_by(SyncRun.id)
            ))

    async def feed(self, number: int) -> SourceFeed:
        async with self.sessions.session() as reader:
            return await reader.get(SourceFeed, self.feeds[number])

    async def test_initial_sync_imports_jobs_memberships_validators_and_runs(self) -> None:
        result = await self.service.sync_all()
        self.assertEqual((result.succeeded, result.not_modified, result.failed, result.rejected), (2, 0, 0, 0))
        first = result.feeds[0]
        self.assertEqual((first.items_seen, first.items_added, first.items_updated, first.items_missing), (3, 3, 0, 0))
        jobs = await self.jobs()
        self.assertEqual(sorted(jobs), ["1", "10", "2", "3"])
        job = jobs["1"]
        self.assertEqual((job.provider, job.title, job.category), ("hzz", "KUHAR/KUHARICA", "UGOSTITELJI, RADNICI U TURIZMU"))
        self.assertEqual(job.canonical_url, "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1")
        self.assertEqual(job.first_seen_at, job.last_seen_at)
        self.assertEqual(await self.memberships(1), {"1": "present", "2": "present", "3": "present"})
        async with self.sessions.session() as reader:
            item = await reader.scalar(select(JobFeedMembership.source_item).join(Job).where(Job.source_job_id == "1"))
        self.assertEqual(item["guid"], "http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1")
        feed = await self.feed(1)
        self.assertEqual(feed.etag, '"v1"')
        self.assertIsNotNone(feed.source_last_modified_at)
        self.assertEqual(feed.last_checked_at, feed.last_success_at)
        self.assertEqual(feed.last_content_change_at, feed.last_success_at)
        run = (await self.runs(1))[-1]
        self.assertEqual((run.status, run.http_status, run.items_seen, run.items_added, run.items_invalid),
                         ("succeeded", 200, 3, 3, 0))
        self.assertGreaterEqual(run.finished_at, run.started_at)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_matching_validators_confirm_presence_without_rewriting_content(self) -> None:
        await self.service.sync_all()
        before = await self.jobs()
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.status, result.http_status, result.items_seen), ("not_modified", 304, 3))
        self.assertEqual(self.requests[-1].headers["if-none-match"], '"v1"')
        after = await self.jobs()
        for key in ("1", "2", "3"):
            self.assertGreater(after[key].last_seen_at, before[key].last_seen_at)
            self.assertEqual(after[key].content_changed_at, before[key].content_changed_at)
        self.assertEqual(after["10"].last_seen_at, before["10"].last_seen_at)
        self.assertEqual([run.status for run in await self.runs(1)], ["succeeded", "not_modified"])
        self.assertEqual((await self.runs(1))[-1].http_status, 304)

    async def test_repeated_identical_download_is_idempotent(self) -> None:
        await self.service.sync_all()
        self.etag[1] = '"v2"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.items_added, result.items_updated, result.items_unchanged), (0, 0, 3))
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count(Job.id))), 4)
            self.assertEqual(await reader.scalar(select(func.count()).select_from(JobFeedMembership)), 4)
        feed = await self.feed(1)
        self.assertEqual(feed.etag, '"v2"')
        self.assertLess(feed.last_content_change_at, feed.last_success_at)

    async def test_changed_content_updates_only_that_job(self) -> None:
        await self.service.sync_all()
        before = await self.jobs()
        self.items[1][1] = ad("2", title="KONOBAR/KONOBARICA")
        self.etag[1] = '"v2"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.items_added, result.items_updated, result.items_unchanged), (0, 1, 2))
        after = await self.jobs()
        self.assertEqual(after["2"].title, "KONOBAR/KONOBARICA")
        self.assertEqual(after["2"].first_seen_at, before["2"].first_seen_at)
        self.assertGreater(after["2"].content_changed_at, before["2"].content_changed_at)
        self.assertNotEqual(after["2"].content_hash, before["2"].content_hash)
        self.assertEqual(after["1"].content_changed_at, before["1"].content_changed_at)
        self.assertEqual((await self.runs(1))[-1].items_updated, 1)

    async def test_disappeared_job_is_marked_missing_and_returns_when_republished(self) -> None:
        await self.service.sync_all()
        self.items[1] = [ad("1"), ad("2")]
        self.etag[1] = '"v2"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.items_seen, result.items_missing), (2, 1))
        self.assertEqual((await self.memberships(1))["3"], "missing")
        self.assertIn("3", await self.jobs())
        async with self.sessions.session() as reader:
            missing = await reader.scalar(select(JobFeedMembership).join(Job).where(Job.source_job_id == "3"))
            self.assertGreaterEqual(missing.missing_since_at, missing.last_seen_at)

        self.items[1] = [ad("1"), ad("2"), ad("3")]
        self.etag[1] = '"v3"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.items_returned, result.items_missing), (1, 0))
        self.assertEqual((await self.memberships(1))["3"], "present")

    async def test_failed_feed_keeps_data_records_failure_and_does_not_stop_others(self) -> None:
        await self.service.sync_all()
        before = await self.feed(1)
        self.status[1] = 503
        self.items[2].append(ad("11"))
        self.etag[2] = '"w2"'
        result = await self.service.sync_all()
        self.assertEqual((result.failed, result.succeeded), (1, 1))
        self.assertEqual((result.feeds[0].status, result.feeds[0].http_status), ("failed", 503))
        self.assertIn("503", result.feeds[0].error)
        self.assertEqual(await self.memberships(1), {"1": "present", "2": "present", "3": "present"})
        self.assertIn("11", await self.jobs())
        run = (await self.runs(1))[-1]
        self.assertEqual((run.status, run.http_status), ("failed", 503))
        self.assertIn("503", run.error_summary)
        feed = await self.feed(1)
        self.assertGreater(feed.last_checked_at, before.last_checked_at)
        self.assertEqual((feed.last_success_at, feed.etag), (before.last_success_at, before.etag))

    async def test_malformed_xml_is_a_failure_that_writes_no_jobs(self) -> None:
        self.items[1] = ["<item><title>broken"]
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.status, result.http_status), ("failed", 200))
        self.assertEqual(await self.jobs(), {})
        self.assertEqual((await self.runs(1))[-1].status, "failed")
        self.assertIsNone((await self.feed(1)).etag)

    async def test_sudden_drop_is_rejected_without_marking_jobs_missing(self) -> None:
        await self.service.sync_all()
        self.items[1] = [ad("1")]
        self.etag[1] = '"v2"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.status, result.items_seen), ("rejected", 1))
        self.assertEqual(await self.memberships(1), {"1": "present", "2": "present", "3": "present"})
        run = (await self.runs(1))[-1]
        self.assertEqual((run.status, run.http_status, run.items_seen), ("rejected", 200, 1))
        self.assertEqual((await self.feed(1)).etag, '"v1"', "A rejected download must be fetched in full again")

    async def test_empty_first_download_is_accepted(self) -> None:
        self.items[1] = []
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual((result.status, result.items_seen), ("succeeded", 0))

    async def test_disabled_feeds_are_skipped_but_can_be_synced_explicitly(self) -> None:
        async with self.sessions.session() as writer:
            (await writer.get(SourceFeed, self.feeds[2])).enabled = False
            await writer.commit()
        result = await self.service.sync_all()
        self.assertEqual([feed.feed_id for feed in result.feeds], [self.feeds[1]])
        self.assertEqual((await self.service.sync_feed(self.feeds[2])).status, "succeeded")

    async def test_unknown_feed_is_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            await self.service.sync_feed(10_000)

    async def test_invalid_retained_ratio_is_rejected(self) -> None:
        for ratio in (-0.1, 1.1, float("nan")):
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                JobSyncService(HzzFeedClient(self.http), HzzFeedParser(), SqlAlchemyUnitOfWorkFactory(self.sessions), ratio)
