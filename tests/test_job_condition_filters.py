from collections import Counter
from datetime import timedelta
from typing import get_args
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, text, update

from model_test_case import ModelTestCase

from FOIHireloom.api.apps.jobs_by_county import MAX_TOP, jobs_by_county
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.models.job import CONDITION_CODES
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.job_conditions import EducationLevel, EmploymentTag
from FOIHireloom.dto.job_market import JobMarketCriteriaDTO, JobMarketFiltersDTO
from FOIHireloom.dto.job_search import JobSearchCriteriaDTO, JobSearchFiltersDTO, UnknownConditionsDTO
from FOIHireloom.exceptions import InvalidJobSearchError
from FOIHireloom.services import CroatianCountyCatalog, JobSearchService

# The plan's example: jobs in Varaždin county for someone without experience who wants a permanent full-time job.
EXAMPLE = dict(county="varazdinska", max_experience_months=0, contract="permanent", full_time=True)


class JobConditionFilterTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.today = await self.session.scalar(text("SELECT (now() AT TIME ZONE 'Europe/Zagreb')::date"))
        counties = {code: County(code=code, name=name) for code, name in (
            ("varazdinska", "Varaždinska županija"), ("istarska", "Istarska županija"),
            ("grad-zagreb", "Grad Zagreb"))}
        self.session.add_all(counties.values())
        await self.session.flush()
        self.county_ids = {code: county.id for code, county in counties.items()}
        feeds = {code: SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label=code, scope="county",
                                  feed_url=f"http://burzarada.hzz.hr/rss/{code}.xml")
                 for code, county in counties.items()}
        self.session.add_all(feeds.values())
        await self.session.flush()
        page = {"page_status": "fetched", "page_checked_at": func.now(), "page_fetched_at": func.now()}
        no_experience = {"experience_months": 0, "trainee": False}
        self.ids = {}
        for key, county, values in (
            ("trainee", "varazdinska", dict(
                experience_months=0, trainee=True, contract="permanent", full_time=True,
                education_levels=["secondary_3", "secondary_4"], accommodation="none",
                employment_tags=["new_position", "trainee"], schedule_tags=["morning", "night"],
                transport_allowance="full", page_work_place="VARAŽDIN, VARAŽDINSKA ŽUPANIJA", **page)),
            ("no_contract", "varazdinska", dict(
                **no_experience, full_time=True, employment_tags=[],
                page_work_place="JALŽABET, VARAŽDINSKA ŽUPANIJA", **page)),
            # The page was read but states neither the experience nor the place of work.
            ("unstated", "varazdinska", dict(contract="permanent", full_time=True, accommodation="shared", **page)),
            # The page was never read; only the feed's municipality is known.
            ("unread", "varazdinska", dict(municipality="VARAŽDIN")),
            ("expired", "varazdinska", dict(
                contract="permanent", full_time=True, page_valid_until=self.today - timedelta(days=1),
                page_work_place="VARAŽDIN, VARAŽDINSKA ŽUPANIJA", **page)),
            ("any", "istarska", dict(
                **no_experience, contract="permanent", full_time=True, education_levels=["primary"],
                accommodation="shared", employment_tags=["new_position"], schedule_tags=["morning"],
                transport_allowance="partial", page_work_place="PULA-POLA, ISTARSKA ŽUPANIJA",
                municipality="PULA - POLA", **page)),
            ("three_years", "istarska", dict(
                experience_months=36, trainee=False, page_work_place="UMAG-UMAGO, ISTARSKA ŽUPANIJA", **page)),
            ("senior", "grad-zagreb", dict(
                experience_months=48, trainee=False, contract="fixed_term", full_time=False, weekly_hours=20,
                education_levels=["university"], accommodation="family", employment_tags=["vacancy", "retirees"],
                page_work_place="ZAGREB-NOVI ZAGREB", **page)),
            ("year", "grad-zagreb", dict(
                experience_months=12, trainee=False, contract="permanent", full_time=True,
                education_levels=["college", "university"], accommodation="single",
                employment_tags=["new_position", "retirees"], page_work_place="SESVETE", **page)),
        ):
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}", content_hash=key,
                      title=f"POSAO {key}", page_source_hash=key if "page_status" in values else None, **values)
            self.session.add(job)
            await self.session.flush()
            self.ids[key] = job.id
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feeds[county].id))
        await self.session.commit()
        self.repository = SqlAlchemyJobRepository(self.session)
        self.service = JobSearchService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)),
                                        CroatianCountyCatalog())

    def criteria(self, **values: object) -> JobSearchCriteriaDTO:
        return JobSearchCriteriaDTO(**{"open_on": self.today, "limit": 50} | values)

    async def found(self, **criteria: object) -> set[str]:
        names = {job_id: key for key, job_id in self.ids.items()}
        return {names[hit.job.id] for hit in await self.repository.search(self.criteria(**criteria))}

    async def keys(self, **filters: object) -> list[str]:
        names = {job_id: key for key, job_id in self.ids.items()}
        return [names[job.id] for job in (await self.service.search(JobSearchFiltersDTO(**filters))).jobs]

    def test_literal_types_match_the_stored_codes(self) -> None:
        self.assertEqual(get_args(EducationLevel.__value__), CONDITION_CODES["education_levels"])
        self.assertEqual(get_args(EmploymentTag.__value__), CONDITION_CODES["employment_tags"])

    async def test_each_condition_filter_leaves_out_unknown_values(self) -> None:
        cases = (
            # Both "Nije važno" and trainee ads need no experience.
            ({"max_experience_months": 0}, {"trainee", "no_contract", "any"}),
            ({"max_experience_months": 12}, {"trainee", "no_contract", "any", "year"}),
            ({"contract": "permanent"}, {"trainee", "unstated", "any", "year"}),
            ({"contract": "other"}, set()),
            ({"full_time": True}, {"trainee", "no_contract", "unstated", "any", "year"}),
            ({"full_time": False}, {"senior"}),
            # Education is the caller's level: a job matches when it accepts that level.
            ({"education": "university"}, {"senior", "year"}),
            ({"education": "secondary_4"}, {"trainee"}),
            ({"accommodation": True}, {"unstated", "any", "senior", "year"}),
            ({"accommodation": False}, {"trainee"}),
            # A job must have every tag.
            ({"employment_tags": ("new_position",)}, {"trainee", "any", "year"}),
            ({"employment_tags": ("new_position", "retirees")}, {"year"}),
            ({"employment_tags": ("trainee", "retirees")}, set()),
            ({"max_experience_months": 0, "contract": "permanent", "full_time": True}, {"trainee", "any"}),
        )
        for criteria, expected in cases:
            with self.subTest(criteria=criteria):
                self.assertEqual(await self.found(**criteria), expected)
        # None of them finds the job whose page was never read.
        self.assertIn("unread", await self.found())

    async def test_place_matches_whole_words_of_the_place_of_work_or_municipality(self) -> None:
        cases = {
            # The page's place without diacritics, and the feed's municipality of an unread page.
            "varazdin": {"trainee", "unread"},
            "pula": {"any"},
            "pola": {"any"},
            "zagreb": {"senior"},
            "novi zagreb": {"senior"},
            "novi": {"senior"},
            "novi sesvete": set(),
            "umag": {"three_years"},
            "sesvete": {"year"},
            # Neither the county after the comma nor a part of a word matches.
            "varazdinska": set(),
            "varazd": set(),
            "rijeci": set(),
        }
        for place, expected in cases.items():
            with self.subTest(place=place):
                self.assertEqual(await self.found(place=place), expected)
        # The place goes into a LIKE pattern, so the criteria accept only words.
        for place in ("pula%", "a_b", "pula ", "pula  pola"):
            with self.subTest(place=place), self.assertRaises(ValidationError):
                self.criteria(place=place)

    async def test_unknown_counts_name_the_jobs_left_out_only_for_unknown_values(self) -> None:
        cases = (
            # The plan's example: the unread job is unknown for all three filters, so it counts under each and
            # once in total; no_contract and unstated are unknown for one. The expired job is not counted.
            ({"county_id": self.county_ids["varazdinska"], "max_experience_months": 0, "contract": "permanent",
              "full_time": True}, {"max_experience_months": 2, "contract": 2, "full_time": 1}, 3),
            # three_years and year need too much experience, so their unknown contract does not count.
            ({"max_experience_months": 0, "contract": "permanent"}, {"max_experience_months": 2, "contract": 2}, 3),
            ({"place": "varazdin"}, {"place": 1}, 1),
            ({"education": "university", "accommodation": True}, {"education": 4, "accommodation": 3}, 4),
            # no_contract has no tags, which is known, so it counts nowhere.
            ({"employment_tags": ("new_position",), "full_time": True}, {"full_time": 2, "employment_tags": 3}, 3),
            ({"place": "varazdin", "county_id": self.county_ids["istarska"]}, {"place": 0}, 0),
            ({}, {}, 0),
        )
        for values, by_filter, total in cases:
            with self.subTest(criteria=values):
                self.assertEqual(await self.repository.count_unknown_conditions(self.criteria(**values)),
                                 UnknownConditionsDTO(by_filter=by_filter, total=total))

    async def test_breakdowns_count_known_normalised_values(self) -> None:
        stats = await self.repository.market_aggregates(JobMarketCriteriaDTO(open_on=self.today, today=self.today,
                                                                             top=10))
        self.assertEqual((stats.jobs, stats.with_details), (8, 7))

        def counts(items) -> dict[str, int]:
            return {item.name: item.jobs for item in items}

        self.assertEqual(counts(stats.contracts), {"permanent": 4, "fixed_term": 1})
        self.assertEqual(counts(stats.employment_tags), {"new_position": 3, "retirees": 2, "trainee": 1, "vacancy": 1})
        self.assertEqual(counts(stats.working_time), {"full_time": 5, "part_time": 1})
        self.assertEqual(counts(stats.experience_bands),
                         {"none": 3, "1_to_12_months": 1, "13_to_36_months": 1, "over_36_months": 1})
        # A job counts once for each level it accepts.
        self.assertEqual(counts(stats.education_levels),
                         {"university": 2, "college": 1, "primary": 1, "secondary_3": 1, "secondary_4": 1})
        self.assertEqual(counts(stats.accommodation), {"shared": 2, "family": 1, "none": 1, "single": 1})
        self.assertEqual(counts(stats.schedule_tags), {"morning": 2, "night": 1})
        self.assertEqual(counts(stats.transport_allowance), {"full": 1, "partial": 1})
        self.assertEqual([item.name for item in stats.contracts], ["permanent", "fixed_term"])
        filtered = await self.repository.market_aggregates(JobMarketCriteriaDTO(
            open_on=self.today, today=self.today, top=10, education="university"))
        self.assertEqual((filtered.jobs, counts(filtered.contracts)), (2, {"fixed_term": 1, "permanent": 1}))

    async def test_example_through_the_service(self) -> None:
        search = await self.service.search(JobSearchFiltersDTO(**EXAMPLE))
        stats = await self.service.market_stats(JobMarketFiltersDTO(**EXAMPLE))
        self.assertEqual([job.source_job_id for job in search.jobs], ["trainee"])
        self.assertEqual(stats.jobs, 1)
        for result in (search, stats):
            self.assertEqual((result.unknown_conditions, result.unknown_total),
                             ({"max_experience_months": 2, "contract": 2, "full_time": 1}, 3))
        unfiltered = await self.service.search(JobSearchFiltersDTO(county="varazdinska"))
        self.assertEqual((unfiltered.unknown_conditions, unfiltered.unknown_total), ({}, 0))

    async def test_place_ignores_case_and_diacritics_and_needs_a_word(self) -> None:
        for place in ("Varaždin", "Varazdin", "VARAŽDIN", " varaždin "):
            with self.subTest(place=place):
                self.assertEqual(set(await self.keys(place=place)), {"trainee", "unread"})
        self.assertEqual(await self.keys(place="Pula-Pola"), ["any"])
        self.assertEqual(await self.keys(place=" "), await self.keys())
        with self.assertRaises(InvalidJobSearchError):
            await self.service.search(JobSearchFiltersDTO(place="!!!"))
        with self.assertRaises(InvalidJobSearchError):
            await self.service.market_stats(JobMarketFiltersDTO(place="--"))

    async def test_invalid_condition_filters_are_rejected(self) -> None:
        for filters in ({"max_experience_months": -1}, {"max_experience_months": 601}, {"contract": "temporary"},
                        {"education": "doctorate"}, {"employment_tags": ("new_position", "remote")},
                        {"full_time": "sometimes"}, {"place": "x" * 201}):
            for dto in (JobSearchFiltersDTO, JobMarketFiltersDTO):
                with self.subTest(dto=dto, filters=filters), self.assertRaises(ValidationError):
                    dto(**filters)
        # No tags is no filter.
        self.assertEqual(await self.keys(employment_tags=()), await self.keys())

    async def test_pages_and_statistics_with_condition_filters_find_the_same_jobs(self) -> None:
        for filters in ({"full_time": True}, {"accommodation": True, "contract": "permanent"},
                        {"query": "posao", "max_experience_months": 12}, {"place": "Varaždin"}):
            with self.subTest(filters=filters):
                everything = await self.service.search(JobSearchFiltersDTO(**filters))
                seen, cursor = [], None
                while True:
                    page = await self.service.search(JobSearchFiltersDTO(**filters, limit=2, cursor=cursor))
                    self.assertEqual((page.unknown_conditions, page.unknown_total),
                                     (everything.unknown_conditions, everything.unknown_total))
                    seen.extend(job.id for job in page.jobs)
                    if (cursor := page.next_cursor) is None:
                        break
                self.assertEqual(seen, [job.id for job in everything.jobs])
                cards = await self.service.search_cards(JobSearchFiltersDTO(**filters))
                stats = await self.service.market_stats(JobMarketFiltersDTO(**filters))
                self.assertEqual([job.id for job in cards.jobs], seen)
                self.assertEqual(stats.jobs, len(seen))
                for result in (cards, stats):
                    self.assertEqual((result.unknown_conditions, result.unknown_total),
                                     (everything.unknown_conditions, everything.unknown_total))

    async def test_condition_filters_combine_with_expired_jobs_categories_and_counties(self) -> None:
        # The expired job is permanent and full-time, but its page does not state the experience.
        expired = await self.service.search(JobSearchFiltersDTO(**EXAMPLE, include_expired=True))
        self.assertEqual([job.source_job_id for job in expired.jobs], ["trainee"])
        self.assertEqual((expired.unknown_conditions, expired.unknown_total),
                         ({"max_experience_months": 3, "contract": 2, "full_time": 1}, 4))
        permanent = dict(county="varazdinska", contract="permanent", full_time=True)
        self.assertEqual(set(await self.keys(**permanent)), {"trainee", "unstated"})
        self.assertEqual(set(await self.keys(**permanent, include_expired=True)), {"trainee", "unstated", "expired"})

        for category, keys in (("UGOSTITELJI, RADNICI U TURIZMU", ("trainee", "any", "year", "unread")),
                               ("POMOĆNI RADNICI", ("senior",))):
            await self.session.execute(update(Job).where(Job.id.in_([self.ids[key] for key in keys])).values(
                category=category, category_source="description"))
        await self.session.commit()
        for filters, keys, unknown in (
            ({"full_time": True}, {"trainee", "any", "year"}, ({"full_time": 1}, 1)),
            # year needs a year of experience; the unread job is unknown for both filters and counts once.
            ({"max_experience_months": 0, "contract": "permanent"}, {"trainee", "any"},
             ({"max_experience_months": 1, "contract": 1}, 1)),
            ({"place": "Pula", "county": "istarska"}, {"any"}, ({"place": 0}, 0)),
        ):
            with self.subTest(filters=filters):
                page = await self.service.search(JobSearchFiltersDTO(category="ugostitelji, radnici u turizmu",
                                                                     **filters))
                self.assertEqual(({job.source_job_id for job in page.jobs}, (page.unknown_conditions,
                                                                            page.unknown_total)), (keys, unknown))

        for filters, keys, unknown in (
            ({"county": "grad-zagreb", "place": "Zagreb"}, {"senior"}, ({"place": 0}, 0)),
            ({"county": "istarska", "place": "Zagreb"}, set(), ({"place": 0}, 0)),
            # The unstated job states no place; the expired one counts only with include_expired.
            ({"county": "varazdinska", "place": "Varaždin"}, {"trainee", "unread"}, ({"place": 1}, 1)),
            ({"county": "varazdinska", "place": "Varaždin", "include_expired": True},
             {"trainee", "unread", "expired"}, ({"place": 1}, 1)),
        ):
            with self.subTest(filters=filters):
                page = await self.service.search(JobSearchFiltersDTO(**filters))
                self.assertEqual(({job.source_job_id for job in page.jobs}, (page.unknown_conditions,
                                                                            page.unknown_total)), (keys, unknown))

    async def test_county_breakdown_and_chart_count_the_jobs_search_finds(self) -> None:
        for filters in ({}, {"full_time": True}, {"place": "Zagreb"}, EXAMPLE, {"education": "university"},
                        {"accommodation": True, "include_expired": True}, {"contract": "other"}):
            with self.subTest(filters=filters):
                search = await self.service.search(JobSearchFiltersDTO(**filters))
                market = JobMarketFiltersDTO(**filters)
                stats = await self.service.market_stats(market)
                chart = jobs_by_county(stats, MAX_TOP, market)
                by_county = dict(Counter(job.county_code for job in search.jobs))
                self.assertEqual({county.code: county.jobs for county in stats.counties}, by_county)
                self.assertEqual({county.code: county.jobs for county in chart.counties}, by_county)
                self.assertEqual((stats.jobs, chart.total_jobs), (len(search.jobs), len(search.jobs)))
                self.assertEqual((chart.unknown_conditions, chart.unknown_total),
                                 (search.unknown_conditions, search.unknown_total))
                if filters == {"full_time": True}:
                    self.assertEqual(by_county, {"varazdinska": 3, "istarska": 1, "grad-zagreb": 1})

    async def test_a_cursor_from_other_filters_continues_after_its_job(self) -> None:
        # A cursor holds only a position in the search order, not the filters that found it. With other
        # condition filters it is valid and continues after that job, so their jobs ordered before it are left
        # out; the unknown counts are those of the filters used.
        first = await self.service.search(JobSearchFiltersDTO(full_time=True, limit=2))
        self.assertEqual([job.source_job_id for job in first.jobs], ["year", "any"])
        for filters, keys, unknown in (
            ({"contract": "permanent"}, ["unstated", "trainee"], ({"contract": 3}, 3)),
            ({"accommodation": True}, ["unstated"], ({"accommodation": 3}, 3)),
            ({"contract": "fixed_term"}, [], ({"contract": 3}, 3)),
        ):
            with self.subTest(filters=filters):
                for method in (self.service.search, self.service.search_cards):
                    page = await method(JobSearchFiltersDTO(**filters, cursor=first.next_cursor))
                    self.assertEqual([job.source_job_id for job in page.jobs], keys)
                    self.assertEqual((page.next_cursor, page.unknown_conditions, page.unknown_total),
                                     (None, *unknown))
        # A cursor from a search with a query still needs a query, whatever the condition filters.
        queried = await self.service.search(JobSearchFiltersDTO(query="posao", full_time=True, limit=1))
        with self.assertRaises(InvalidJobSearchError):
            await self.service.search(JobSearchFiltersDTO(full_time=True, cursor=queried.next_cursor))

    async def test_a_job_accepting_several_levels_is_found_by_each_and_counted_once(self) -> None:
        job = Job(provider="hzz", source_job_id="multi", canonical_url="https://example.com/multi",
                  content_hash="multi", page_source_hash="multi", title="POSAO multi", page_status="fetched",
                  page_checked_at=func.now(), page_fetched_at=func.now(), experience_months=0, trainee=False,
                  full_time=True, education_levels=["secondary_4", "college", "university"], accommodation="none",
                  employment_tags=["new_position"], page_work_place="ZAGREB-DUBRAVA, GRAD ZAGREB")
        self.session.add(job)
        await self.session.flush()
        feed = await self.session.scalar(text("SELECT id FROM source_feeds WHERE label = 'grad-zagreb'"))
        self.session.add(JobFeedMembership(job_id=job.id, feed_id=feed))
        await self.session.commit()
        self.ids["multi"] = job.id
        for level, keys in (("secondary_4", {"multi"}), ("college", {"multi", "year"}),
                            ("university", {"multi", "year", "senior"})):
            with self.subTest(level=level):
                filters = dict(county="grad-zagreb", education=level)
                self.assertEqual(set(await self.keys(**filters)), keys)
                stats = await self.service.market_stats(JobMarketFiltersDTO(**filters))
                self.assertEqual(stats.jobs, len(keys))
                # Its contract is unknown, so it is left out once, whichever of its levels matched.
                page = await self.service.search(JobSearchFiltersDTO(**filters, contract="permanent"))
                self.assertEqual((page.unknown_conditions, page.unknown_total), ({"education": 0, "contract": 1}, 1))
        stats = await self.service.market_stats(JobMarketFiltersDTO(county="grad-zagreb", full_time=True))
        self.assertEqual((stats.jobs, {item.name: item.jobs for item in stats.education_levels}),
                         (2, {"university": 2, "college": 2, "secondary_4": 1}))
        # "Zagreb" finds "ZAGREB-DUBRAVA".
        self.assertEqual(set(await self.keys(place="Zagreb")), {"multi", "senior"})
