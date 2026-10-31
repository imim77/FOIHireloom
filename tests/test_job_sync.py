from uuid import uuid4

import httpx
from sqlalchemy import func, select

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed, SyncRun
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.exceptions import NotFoundError
from FOIHireloom.integrations.concrete.hzz_feed import HzzFeedClient
from FOIHireloom.services import FeedCategoryVerifier, HzzFeedParser, JobSyncService


CATERING = "UGOSTITELJI, RADNICI U TURIZMU"


def ad(web_sifra: str, title: str = "KUHAR/KUHARICA", deadline: str = "30.11.2026",
       category: str | None = CATERING) -> str:
    link = f"http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra={web_sifra}"
    category_field = f"Kategorija: {category}, " if category else ""
    description = (f"Opis posla: {title}, {category_field}Rok za prijavu: {deadline}, "
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
        self.assertEqual((job.location_text, job.municipality), ("BJELOVAR", "BJELOVAR"))
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

    async def add_occupation_feed(self) -> None:
        feed = SourceFeed(ckan_resource_id=uuid4(), label="Zanimanje", scope="occupation",
                          feed_url="http://burzarada.hzz.hr/rss/rsszup3.xml")
        self.session.add(feed)
        await self.session.commit()
        self.feeds[3] = feed.id
        self.status[3], self.etag[3] = 200, '"k1"'

    async def test_occupation_feed_links_known_jobs_without_creating_or_changing_them(self) -> None:
        await self.add_occupation_feed()
        self.items[3] = [ad("1"), ad("10", title="KONOBAR/KONOBARICA"), ad("99")]
        result = await self.service.sync_all()
        occupation = result.feeds[-1]
        self.assertEqual(occupation.feed_id, self.feeds[3])
        self.assertEqual(
            (occupation.status, occupation.items_seen, occupation.items_added, occupation.items_updated,
             occupation.items_unchanged, occupation.items_unlinked),
            ("succeeded", 3, 0, 0, 2, 1),
        )
        jobs = await self.jobs()
        self.assertEqual(sorted(jobs), ["1", "10", "2", "3"])
        self.assertEqual(jobs["10"].title, "KUHAR/KUHARICA")
        self.assertEqual(await self.memberships(3), {"1": "present", "10": "present"})
        run = (await self.runs(3))[-1]
        self.assertEqual((run.items_seen, run.items_added, run.items_updated), (3, 0, 0))
        feed = await self.feed(3)
        self.assertEqual(feed.last_content_change_at, feed.last_success_at)

        for etag in ('"k1"', '"k2"'):
            with self.subTest(etag=etag):
                self.etag[3] = etag
                result = await self.service.sync_feed(self.feeds[3])
                self.assertEqual(result.status, "not_modified" if etag == '"k1"' else "succeeded")
                after = await self.jobs()
                for key in ("1", "10"):
                    self.assertEqual(after[key].last_seen_at, jobs[key].last_seen_at)
                    self.assertEqual(after[key].content_changed_at, jobs[key].content_changed_at)

    async def test_occupation_feed_links_a_job_once_a_county_feed_imports_it(self) -> None:
        await self.add_occupation_feed()
        self.items[3] = [ad("1"), ad("99")]
        await self.service.sync_all()
        self.assertEqual(await self.memberships(3), {"1": "present"})

        self.items[1].append(ad("99"))
        self.items[3] = [ad("99")]
        self.etag[1], self.etag[3] = '"v2"', '"k2"'
        result = await self.service.sync_all()
        self.assertEqual((result.feeds[-1].items_unlinked, result.feeds[-1].items_missing), (0, 1))
        self.assertEqual(await self.memberships(3), {"1": "missing", "99": "present"})
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count(Job.id)).where(Job.source_job_id == "99")), 1)

    async def test_occupation_feed_download_verifies_its_category_mapping(self) -> None:
        await self.add_occupation_feed()
        self.items[3] = [ad("1"), ad("2", category=None), ad("99")]
        result = await self.service.sync_all()
        self.assertTrue(all(feed.category_mapping is None for feed in result.feeds[:-1]))
        mapping = result.feeds[-1].category_mapping
        self.assertEqual((mapping.category, mapping.status, mapping.matching_examples, mapping.contradicting_examples),
                         (CATERING, "too_few_examples", 2, 0))
        feed = await self.feed(3)
        self.assertEqual((feed.mapped_category, feed.mapping_status), (CATERING, "too_few_examples"))
        self.assertEqual(feed.mapping_verified_at, feed.last_success_at)
        self.assertIsNone((await self.feed(1)).mapping_status)

        verified_at = feed.mapping_verified_at
        result = await self.service.sync_feed(self.feeds[3])
        self.assertEqual((result.status, result.category_mapping), ("not_modified", None))
        self.assertEqual((await self.feed(3)).mapping_verified_at, verified_at)

        for items, expected in (
            ([ad("1"), ad("2"), ad("99")], ("confirmed", 3, 0)),
            ([ad("1"), ad("2"), ad("99"), ad("3", category="STRUČNJACI U PROMETU")], ("contradicted", 3, 1)),
        ):
            with self.subTest(expected=expected):
                self.items[3], self.etag[3] = items, f'"{expected[0]}"'
                result = await self.service.sync_feed(self.feeds[3])
                feed = await self.feed(3)
                self.assertEqual(
                    (feed.mapped_category, feed.mapping_status, feed.mapping_matching_examples,
                     feed.mapping_contradicting_examples), (CATERING, *expected),
                )
                self.assertGreater(feed.mapping_verified_at, verified_at)
                self.assertEqual(result.category_mapping.status, expected[0])

    async def test_unverified_occupation_feed_is_downloaded_in_full(self) -> None:
        await self.add_occupation_feed()
        self.items[3] = [ad("1")]
        async with self.sessions.session() as writer:
            feed = await writer.get(SourceFeed, self.feeds[3])
            feed.etag = '"k1"'
            await writer.commit()
        await self.service.sync_all()
        self.assertNotIn("if-none-match", self.requests[-1].headers)
        self.assertEqual((await self.feed(3)).mapping_status, "too_few_examples")
        result = await self.service.sync_feed(self.feeds[3])
        self.assertEqual(self.requests[-1].headers["if-none-match"], '"k1"')
        self.assertEqual(result.status, "not_modified")

    async def test_min_examples_decides_when_a_mapping_is_confirmed(self) -> None:
        await self.add_occupation_feed()
        self.items[3] = [ad("1")]
        service = JobSyncService(HzzFeedClient(self.http), HzzFeedParser(), SqlAlchemyUnitOfWorkFactory(self.sessions),
                                 category_verifier=FeedCategoryVerifier(1))
        result = await service.sync_feed(self.feeds[3])
        self.assertEqual(result.category_mapping.status, "confirmed")

    async def test_description_category_wins_and_empty_reimport_keeps_the_category(self) -> None:
        await self.add_occupation_feed()
        self.items[1], self.items[3] = [ad("1"), ad("2", category=None), ad("3")], []
        await self.service.sync_all()
        jobs = await self.jobs()
        self.assertEqual((jobs["1"].category, jobs["1"].category_source, jobs["1"].category_feed_id),
                         (CATERING, "description", None))
        self.assertEqual((jobs["2"].category, jobs["2"].category_source), (None, None))
        async with self.sessions.session() as writer:
            filled = await writer.get(Job, jobs["3"].id)
            filled.category, filled.category_source, filled.category_feed_id = "TEKSTILCI I KOŽARI", "feed", self.feeds[3]
            await writer.commit()

        self.items[1] = [ad("1", title="KONOBAR", category=None), ad("2", category="STRUČNJACI U PROMETU"),
                         ad("3", title="KONOBAR", category=None)]
        self.etag[1] = '"v2"'
        result = await self.service.sync_feed(self.feeds[1])
        self.assertEqual(result.items_updated, 3)
        jobs = await self.jobs()
        self.assertEqual((jobs["1"].title, jobs["1"].category, jobs["1"].category_source), ("KONOBAR", CATERING, "description"))
        self.assertEqual((jobs["2"].category, jobs["2"].category_source), ("STRUČNJACI U PROMETU", "description"))
        self.assertEqual((jobs["3"].category, jobs["3"].category_source, jobs["3"].category_feed_id),
                         ("TEKSTILCI I KOŽARI", "feed", self.feeds[3]))

        self.items[1][2] = ad("3")
        self.etag[1] = '"v3"'
        await self.service.sync_feed(self.feeds[1])
        job = (await self.jobs())["3"]
        self.assertEqual((job.category, job.category_source, job.category_feed_id), (CATERING, "description", None))
