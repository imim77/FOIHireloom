import base64
from datetime import date, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, text

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.job_search import JobSearchCriteriaDTO, JobSearchFiltersDTO
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services import CroatianCountyCatalog, JobSearchService

HOSPITALITY = "UGOSTITELJI, RADNICI U TURIZMU"


class JobSearchServiceTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.today = await self.session.scalar(text("SELECT (now() AT TIME ZONE 'Europe/Zagreb')::date"))
        counties = {
            code: County(code=code, name=name)
            for code, name in (
                ("bjelovarsko-bilogorska", "Bjelovarsko-bilogorska županija"),
                ("grad-zagreb", "Grad Zagreb"),
                ("istarska", "Istarska županija"),
            )
        }
        self.session.add_all(counties.values())
        await self.session.flush()
        feeds = {
            name: SourceFeed(county_id=counties[code].id, ckan_resource_id=uuid4(), label=name, scope="county",
                             feed_url=f"http://burzarada.hzz.hr/rss/{name}.xml")
            for name, code in (("bj1", "bjelovarsko-bilogorska"), ("bj2", "bjelovarsko-bilogorska"),
                               ("zg", "grad-zagreb"))
        }
        self.session.add_all(feeds.values())
        await self.session.flush()
        self.ids = {}
        for key, values, listings in (
            ("cook", dict(title="KUHAR/KUHARICA", description_text="Rad u restoranu.", category=HOSPITALITY,
                          published_on=date(2026, 10, 27)), {"bj1": "present", "bj2": "present"}),
            ("cleaner", dict(title="ČISTAČICA", category="POMOĆNI RADNICI", published_on=date(2026, 10, 28),
                             deadline_on=self.today - timedelta(days=1)), {"zg": "present"}),
            ("driver", dict(title="VOZAČ C KATEGORIJE", published_on=date(2026, 10, 28),
                            deadline_on=self.today + timedelta(days=30)), {"zg": "present"}),
            ("gone", dict(title="KUHAR", category=HOSPITALITY, published_on=date(2026, 10, 29)), {"zg": "missing"}),
            ("waiter", dict(title="KONOBAR", category=HOSPITALITY, published_on=None), {"bj1": "present"}),
            ("nurse", dict(title="MEDICINSKA SESTRA", published_on=date(2026, 10, 26), deadline_on=self.today,
                           quality_flags=["description_truncated"]), {"zg": "present"}),
        ):
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}",
                      content_hash=key, **values)
            self.session.add(job)
            await self.session.flush()
            self.ids[key] = job.id
            for feed, status in listings.items():
                self.session.add(JobFeedMembership(
                    job_id=job.id, feed_id=feeds[feed].id, presence_status=status,
                    missing_since_at=func.now() if status == "missing" else None,
                ))
        await self.session.commit()
        self.service = JobSearchService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)),
                                        CroatianCountyCatalog())

    async def keys(self, **filters: object) -> list[str]:
        page = await self.service.search(JobSearchFiltersDTO(**filters))
        names = {job_id: key for key, job_id in self.ids.items()}
        return [names[job.id] for job in page.jobs]

    async def test_default_search_lists_open_jobs_once_newest_first(self) -> None:
        # Unknown publication dates come last; a deadline of today is still open.
        self.assertEqual(await self.keys(), ["driver", "cook", "nurse", "waiter"])
        page = await self.service.search(JobSearchFiltersDTO())
        cook = next(job for job in page.jobs if job.id == self.ids["cook"])
        self.assertEqual((cook.title, cook.category, cook.canonical_url), ("KUHAR/KUHARICA", HOSPITALITY,
                                                                           "https://example.com/cook"))
        self.assertIsNone(cook.deadline_passed)
        self.assertIsNone(page.next_cursor)

    async def test_include_expired_marks_passed_deadlines(self) -> None:
        self.assertEqual(await self.keys(include_expired=True), ["driver", "cleaner", "cook", "nurse", "waiter"])
        page = await self.service.search(JobSearchFiltersDTO(include_expired=True))
        passed = {job.id: job.deadline_passed for job in page.jobs}
        self.assertEqual((passed[self.ids["cleaner"]], passed[self.ids["nurse"]], passed[self.ids["cook"]]),
                         (True, False, None))

    async def test_query_matches_word_prefixes_with_or_without_diacritics(self) -> None:
        cases = {
            "kuhar": ["cook"],
            "KUH": ["cook"],
            "kuhar restoranu": ["cook"],
            "kuhar vozač": [],
            "vozac": ["driver"],
            "Vozač  C": ["driver"],
            "čistačica": ["cleaner"],
            "cistac": ["cleaner"],
            "a:* | b & !c": [],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(await self.keys(query=query, include_expired=True), expected)
        for query in ("", "   "):
            self.assertEqual(len(await self.keys(query=query)), 4)
        with self.assertRaises(InvalidJobSearchError):
            await self.service.search(JobSearchFiltersDTO(query="!!! --"))

    async def test_county_accepts_code_or_name(self) -> None:
        for county in ("grad-zagreb", "Grad Zagreb", "GRAD-ZAGREB"):
            with self.subTest(county=county):
                self.assertEqual(await self.keys(county=county), ["driver", "nurse"])
        self.assertEqual(await self.keys(county="Bjelovarsko-bilogorska županija"), ["cook", "waiter"])
        self.assertEqual(await self.keys(county="istarska"), [])
        with self.assertRaises(NotFoundError):
            await self.service.search(JobSearchFiltersDTO(county="Atlantida"))

    async def test_category_matches_exactly_ignoring_case(self) -> None:
        self.assertEqual(await self.keys(category="ugostitelji, radnici u turizmu"), ["cook", "waiter"])
        self.assertEqual(await self.keys(category="UGOSTITELJI"), [])
        self.assertEqual(await self.keys(category=" "), await self.keys())

    async def test_cursor_pages_through_every_result_once(self) -> None:
        seen, cursor = [], None
        while True:
            page = await self.service.search(JobSearchFiltersDTO(limit=1, cursor=cursor, include_expired=True))
            seen.extend(job.id for job in page.jobs)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        everything = await self.service.search(JobSearchFiltersDTO(include_expired=True))
        self.assertEqual(seen, [job.id for job in everything.jobs])
        two = await self.service.search(JobSearchFiltersDTO(limit=2))
        rest = await self.service.search(JobSearchFiltersDTO(limit=2, cursor=two.next_cursor))
        self.assertEqual([job.id for job in two.jobs + rest.jobs], [self.ids[key] for key in await self.keys()])
        self.assertIsNone(rest.next_cursor)

    async def test_malformed_cursor_or_filters_are_rejected(self) -> None:
        for cursor in ("abc", "čžš", base64.urlsafe_b64encode(b'{"id": "x"}').decode(),
                       base64.urlsafe_b64encode(b'{"published_on": null, "id": 0}').decode()):
            with self.subTest(cursor=cursor), self.assertRaises(InvalidJobSearchError):
                await self.service.search(JobSearchFiltersDTO(cursor=cursor))
        for filters in ({"limit": 0}, {"limit": 21}, {"query": "x" * 201}):
            with self.subTest(filters=filters), self.assertRaises(ValidationError):
                JobSearchFiltersDTO(**filters)
        with self.assertRaises(ValidationError):
            JobSearchCriteriaDTO(terms=("kuhar:*",), limit=1)

    async def test_get_job_returns_unlisted_jobs_with_their_listings(self) -> None:
        gone = await self.service.get_job(self.ids["gone"])
        self.assertEqual((gone.title, gone.source_job_id, gone.availability_status), ("KUHAR", "gone", "unknown"))
        self.assertEqual([(listing.county_code, listing.presence_status) for listing in gone.listings],
                         [("grad-zagreb", "missing")])
        self.assertIsNotNone(gone.listings[0].missing_since_at)
        cook = await self.service.get_job(self.ids["cook"])
        self.assertEqual(cook.description_text, "Rad u restoranu.")
        self.assertEqual([listing.county_name for listing in cook.listings], ["Bjelovarsko-bilogorska županija"] * 2)
        nurse = await self.service.get_job(self.ids["nurse"])
        self.assertEqual((nurse.deadline_passed, nurse.quality_flags), (False, ("description_truncated",)))
        with self.assertRaises(NotFoundError):
            await self.service.get_job(max(self.ids.values()) + 1)

    async def test_regions_and_categories_count_what_default_search_finds(self) -> None:
        regions = await self.service.list_regions()
        self.assertEqual([(region.code, region.open_jobs) for region in regions],
                         [("bjelovarsko-bilogorska", 2), ("grad-zagreb", 2), ("istarska", 0)])
        categories = await self.service.list_categories()
        self.assertEqual([(category.name, category.open_jobs) for category in categories], [(HOSPITALITY, 2)])
