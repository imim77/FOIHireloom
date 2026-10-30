import base64
from datetime import date, datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, text, update

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.job_search import JobSearchCriteriaDTO, JobSearchFiltersDTO, JobSummaryDTO
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
                             feed_url=f"http://burzarada.hzz.hr/rss/{name}.xml", last_checked_at=func.now(),
                             last_success_at=func.now())
            for name, code in (("bj1", "bjelovarsko-bilogorska"), ("bj2", "bjelovarsko-bilogorska"),
                               ("zg", "grad-zagreb"))
        }
        self.session.add_all(feeds.values())
        await self.session.flush()
        self.feed_ids = {name: feed.id for name, feed in feeds.items()}
        self.ids = {}
        for key, values, listings in (
            ("cook", dict(title="KUHAR/KUHARICA", description_text="Rad u restoranu.", category=HOSPITALITY,
                          published_on=date(2026, 10, 27)), {"bj1": "present", "bj2": "present"}),
            ("cleaner", dict(title="ČISTAČICA", category="POMOĆNI RADNICI", published_on=date(2026, 10, 28),
                             deadline_on=self.today - timedelta(days=1)), {"zg": "present"}),
            ("driver", dict(title="VOZAČ C KATEGORIJE", location_text="ZAGREB", published_on=date(2026, 10, 28),
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

    async def set_feed(self, name: str, *, success_hours_ago: float | None = 0, enabled: bool = True) -> None:
        """Move a feed's last success into the past, or clear it with None."""
        success = None if success_hours_ago is None else func.now() - timedelta(hours=success_hours_ago)
        await self.session.execute(update(SourceFeed).where(SourceFeed.id == self.feed_ids[name]).values(
            last_success_at=success, enabled=enabled))
        await self.session.commit()

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

    async def test_query_searches_job_page_text_and_puts_title_matches_first(self) -> None:
        # The driver is newer than the cook, but only its page mentions cooks.
        await self.set_page("driver", page_description_text="Dostava hrane kuharima u Đakovu.",
                            page_employer_name="PLODINE d.d.", page_work_place="PULA-POLA, ISTARSKA ŽUPANIJA",
                            page_education="Srednja škola 3 godine")
        for query in ("dakovu", "plodine", "pula", "srednja skola"):
            with self.subTest(query=query):
                self.assertEqual(await self.keys(query=query), ["driver"])
        page = await self.service.search(JobSearchFiltersDTO(query="kuhar"))
        self.assertEqual([(job.source_job_id, job.title_match) for job in page.jobs], [("cook", True), ("driver", False)])
        # Every term must be in the title for a title match.
        page = await self.service.search(JobSearchFiltersDTO(query="kuhar restoranu"))
        self.assertEqual([(job.source_job_id, job.title_match) for job in page.jobs], [("cook", False)])
        self.assertIsNone((await self.service.search(JobSearchFiltersDTO())).jobs[0].title_match)

        seen, cursor = [], None
        while True:
            page = await self.service.search(JobSearchFiltersDTO(query="kuhar", limit=1, cursor=cursor))
            seen.extend(job.source_job_id for job in page.jobs)
            if (cursor := page.next_cursor) is None:
                break
        self.assertEqual(seen, ["cook", "driver"])

    async def test_cursor_must_come_from_a_search_with_or_without_a_query_alike(self) -> None:
        plain = (await self.service.search(JobSearchFiltersDTO(limit=1))).next_cursor
        queried = (await self.service.search(JobSearchFiltersDTO(query="k", limit=1, include_expired=True))).next_cursor
        self.assertIsNotNone(queried)
        for filters in ({"query": "kuhar", "cursor": plain}, {"cursor": queried}):
            with self.subTest(filters=filters), self.assertRaises(InvalidJobSearchError):
                await self.service.search(JobSearchFiltersDTO(**filters))

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

    async def test_coverage_names_counties_without_fresh_data(self) -> None:
        coverage = (await self.service.search(JobSearchFiltersDTO())).coverage
        # Istarska has no feed at all, so its jobs cannot be in the results.
        self.assertEqual(coverage.data_status, "unavailable")
        self.assertEqual([(region.code, region.data_status, region.last_success_at) for region in
                          coverage.affected_regions], [("istarska", "unavailable", None)])
        self.assertIn("1 of 3 counties", coverage.warning)
        self.assertIn("Istarska županija (never loaded)", coverage.warning)
        self.assertEqual(coverage.stale_after_hours, 6)
        zagreb = (await self.service.search(JobSearchFiltersDTO(county="grad-zagreb"))).coverage
        self.assertEqual((zagreb.data_status, zagreb.affected_regions, zagreb.warning), ("fresh", (), None))
        self.assertIsInstance(zagreb.data_as_of, datetime)

    async def test_old_or_missing_feed_success_makes_a_county_stale_or_unavailable(self) -> None:
        await self.set_feed("zg", success_hours_ago=7)
        zagreb = (await self.service.search(JobSearchFiltersDTO(county="Grad Zagreb"))).coverage
        self.assertEqual(zagreb.data_status, "stale")
        self.assertRegex(zagreb.warning, r"^Job data for the requested county was not updated in the last 6 hours")
        self.assertRegex(zagreb.warning, r"Grad Zagreb \(last updated \d{4}-\d\d-\d\d \d\d:\d\d UTC\)")
        self.assertEqual(zagreb.data_as_of, zagreb.affected_regions[0].last_success_at)
        # The results themselves are unchanged; only the warning tells them apart.
        self.assertEqual(await self.keys(county="Grad Zagreb"), ["driver", "nurse"])

        await self.set_feed("bj2", success_hours_ago=None)
        regions = {region.code: region for region in await self.service.list_regions()}
        self.assertEqual({code: region.data_status for code, region in regions.items()},
                         {"bjelovarsko-bilogorska": "unavailable", "grad-zagreb": "stale", "istarska": "unavailable"})
        self.assertIsNotNone(regions["bjelovarsko-bilogorska"].last_success_at)
        self.assertEqual(regions["bjelovarsko-bilogorska"].open_jobs, 2)
        warning = (await self.service.search(JobSearchFiltersDTO())).coverage.warning
        self.assertIn("3 of 3 counties", warning)
        self.assertIn("UTC, a feed never loaded)", warning)

        # A disabled feed is not expected to update, so it no longer counts.
        await self.set_feed("bj2", success_hours_ago=None, enabled=False)
        bjelovar = (await self.service.search(JobSearchFiltersDTO(county="bjelovarsko-bilogorska"))).coverage
        self.assertEqual(bjelovar.data_status, "fresh")

    async def test_regions_and_listings_report_feed_freshness(self) -> None:
        await self.set_feed("bj1", success_hours_ago=8)
        regions = {region.code: region for region in await self.service.list_regions()}
        self.assertEqual((regions["grad-zagreb"].data_status, regions["bjelovarsko-bilogorska"].data_status),
                         ("fresh", "stale"))
        self.assertIsNone(regions["istarska"].last_success_at)
        cook = await self.service.get_job(self.ids["cook"])
        self.assertEqual(sorted(listing.data_status for listing in cook.listings), ["fresh", "stale"])
        self.assertTrue(all(listing.feed_last_success_at for listing in cook.listings))

    async def test_jobs_without_a_title_get_a_neutral_display_title(self) -> None:
        page = await self.service.search(JobSearchFiltersDTO(query="kuhar"))
        self.assertEqual(page.jobs[0].display_title, "KUHAR/KUHARICA")
        untitled = page.jobs[0].model_copy(update={"title": None, "source_job_id": "167397641"})
        self.assertEqual(untitled.display_title, "Oglas HZZ 167397641")
        self.assertEqual(JobSummaryDTO.model_validate(untitled.model_dump() | {"source_job_id": None}).display_title,
                         f"Oglas HZZ bez naslova ({untitled.id})")
        with self.assertRaises(ValueError):
            JobSearchService(lambda: None, CroatianCountyCatalog(), timedelta(0))

    async def test_every_listed_job_has_a_display_location(self) -> None:
        page = await self.service.search(JobSearchFiltersDTO(include_expired=True))
        locations = {job.source_job_id: (job.county_code, job.display_location) for job in page.jobs}
        self.assertEqual(locations["driver"], ("grad-zagreb", "ZAGREB, Grad Zagreb"))
        # HZZ gave no town for the cook, so the county from its feed is the most precise location.
        self.assertEqual(locations["cook"], ("bjelovarsko-bilogorska",
                                             "Bjelovarsko-bilogorska županija (mjesto rada nije navedeno)"))
        self.assertTrue(all(job.county_name for job in page.jobs))
        gone = await self.service.get_job(self.ids["gone"])
        self.assertEqual((gone.county_name, gone.display_location),
                         ("Grad Zagreb", "Grad Zagreb (mjesto rada nije navedeno)"))
        self.assertEqual(page.jobs[0].model_copy(update={"location_text": None, "county_name": None}).display_location,
                         "Mjesto rada nije navedeno")

    async def set_page(self, key: str, **values: object) -> None:
        await self.session.execute(update(Job).where(Job.id == self.ids[key]).values(
            page_status="fetched", page_checked_at=func.now(), page_fetched_at=func.now(), page_source_hash=key,
            **values))
        await self.session.commit()

    async def test_job_page_values_take_precedence_over_the_feed(self) -> None:
        # The feed's deadline for the cleaner has passed, but its page says the job is still open.
        await self.set_page("cleaner", page_valid_until=self.today + timedelta(days=5),
                            page_work_place="SESVETE, GRAD ZAGREB")
        # The feed gave the cook no deadline; its page says the deadline was yesterday.
        await self.set_page("cook", page_valid_until=self.today - timedelta(days=1), page_title="KUHAR/KUHARICA - SAMOSTALNI",
                            page_work_place="BJELOVAR, BJELOVARSKO-BILOGORSKA ŽUPANIJA", page_employer_name="HOTEL d.o.o.",
                            page_description_text="Puni opis posla.", page_employment_type="Na neodređeno")
        await self.set_page("nurse", page_description_text="Cijeli opis.", page_work_place="ZAGREB")
        self.assertEqual(await self.keys(), ["driver", "cleaner", "nurse", "waiter"])

        page = await self.service.search(JobSearchFiltersDTO(include_expired=True))
        jobs = {job.source_job_id: job for job in page.jobs}
        cleaner, cook, nurse = jobs["cleaner"], jobs["cook"], jobs["nurse"]
        self.assertEqual((cleaner.deadline_on, cleaner.deadline_source, cleaner.deadline_passed),
                         (self.today + timedelta(days=5), "job_page", False))
        self.assertEqual(cleaner.display_location, "SESVETE, GRAD ZAGREB")
        self.assertEqual((cook.title, cook.deadline_source, cook.deadline_passed, cook.employer_name),
                         ("KUHAR/KUHARICA - SAMOSTALNI", "job_page", True, "HOTEL d.o.o."))
        self.assertEqual(cook.display_location, "BJELOVAR, BJELOVARSKO-BILOGORSKA ŽUPANIJA")
        # The feed's deadline stays in use when the page has none; Zagreb's page omits the county.
        self.assertEqual((nurse.deadline_on, nurse.deadline_source, nurse.display_location),
                         (self.today, "feed", "ZAGREB, Grad Zagreb"))
        self.assertEqual(nurse.quality_flags, ())
        self.assertEqual((jobs["driver"].details_status, jobs["driver"].deadline_source), ("pending", "feed"))
        self.assertIsNone(jobs["waiter"].deadline_source)

        details = await self.service.get_job(self.ids["cook"])
        self.assertEqual((details.description_text, details.description_source, details.employment_type),
                         ("Puni opis posla.", "job_page", "Na neodređeno"))
        self.assertEqual(details.details_status, "fetched")
        self.assertIsNotNone(details.details_checked_at)
        feed_only = await self.service.get_job(self.ids["driver"])
        self.assertEqual((feed_only.description_source, feed_only.employment_type, feed_only.details_checked_at),
                         (None, None, None))
        self.assertEqual((await self.service.get_job(self.ids["gone"])).description_source, None)
        regions = {region.code: region.open_jobs for region in await self.service.list_regions()}
        self.assertEqual(regions["bjelovarsko-bilogorska"], 1)
