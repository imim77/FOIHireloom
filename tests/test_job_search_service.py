import base64
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from FOIHireloom.config.settings import Settings
from FOIHireloom.dao.interfaces.job import JobSearchHit
from FOIHireloom.db.models import Job
from FOIHireloom.domain.job_search import JobCursorCodec, condition_criteria, local_date, search_terms
from FOIHireloom.dto.job_comparison import JobComparisonConditionsDTO
from FOIHireloom.dto.job_search import (
    CountyFeedCheckDTO, JobConditionFiltersDTO, JobCountyDTO, JobSearchFiltersDTO, UnknownConditionsDTO,
)
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.factories.job_search import JobSearchServiceFactory
from FOIHireloom.services.concrete.job_presentation import JobPresenter

NOW = datetime(2026, 11, 3, 23, 30, tzinfo=UTC)
TODAY = date(2026, 11, 4)


def job(job_id: int = 1, **changes) -> Job:
    values = dict(
        id=job_id, source_job_id=str(job_id), title="Feed title", category=None,
        location_text=None, municipality=None, published_on=date(2026, 11, 1), deadline_on=None,
        canonical_url=f"https://example.com/jobs/{job_id}", quality_flags=["title_truncated", "deadline_unknown"],
        last_seen_at=NOW, first_seen_at=NOW, content_changed_at=NOW, page_status="pending",
        description_text="Feed description", conditions_unrecognised=[],
    )
    return Job(**(values | changes))


class SearchRuleTests(unittest.TestCase):
    def test_words_fold_stem_and_deduplicate_without_sql_operators(self) -> None:
        self.assertEqual(search_terms("KUHARICA kuhar, čistačica"), ("kuhar", "cistac"))
        self.assertEqual(search_terms(None), ())
        self.assertEqual(search_terms("  "), ())
        with self.assertRaises(InvalidJobSearchError):
            search_terms(" & | / ")
        filters = JobConditionFiltersDTO(place="  PULA-POLA,  ", employment_tags=(), full_time=False)
        normalized = condition_criteria(filters)
        self.assertEqual((normalized["place"], normalized["employment_tags"], normalized["full_time"]),
                         ("pula pola", None, False))
        self.assertEqual(filters.place, "  PULA-POLA,  ")
        with self.assertRaises(InvalidJobSearchError):
            condition_criteria(JobConditionFiltersDTO(place="_%"))

    def test_cursor_round_trips_unknown_dates_and_title_ranking_and_rejects_invalid_input(self) -> None:
        codec, presenter = JobCursorCodec(), JobPresenter()
        for published in (None, date(2026, 11, 1)):
            for title_match in (None, False, True):
                summary = presenter.summary(job(published_on=published), TODAY, None, title_match)
                decoded = codec.decode(codec.encode(summary))
                self.assertEqual((decoded.id, decoded.published_on, decoded.title_match), (1, published, title_match))
        for cursor in ("%", "ž", base64.urlsafe_b64encode(b'{"id":0,"published_on":null}').decode()):
            with self.subTest(cursor=cursor), self.assertRaises(InvalidJobSearchError):
                codec.decode(cursor)

    def test_calendar_day_uses_croatian_time_in_winter_and_summer(self) -> None:
        self.assertEqual(local_date(NOW), TODAY)
        self.assertEqual(local_date(datetime(2026, 7, 1, 22, 30, tzinfo=UTC)), date(2026, 7, 2))

    def test_skills_are_optional_and_duplicate_requests_count_once(self) -> None:
        self.assertIsNone(condition_criteria(JobConditionFiltersDTO(skills=()))["skills"])
        filters = JobConditionFiltersDTO(skills=("csharp", "python", "csharp"))
        self.assertEqual(condition_criteria(filters)["skills"], ("csharp", "python"))

    def test_skill_cursor_preserves_the_number_of_requested_matches(self) -> None:
        presenter, codec = JobPresenter(), JobCursorCodec()
        summary = presenter.summary(job(skills=["python", "csharp", "sql"]), TODAY, None, False,
                                    ("csharp", "python", "csharp"))
        self.assertEqual(summary.matched_skills, ("csharp", "python"))
        self.assertEqual(codec.decode(codec.encode(summary)).skill_matches, 2)
        self.assertEqual(presenter.card(job(skills=["sql"]), TODAY, None, None, ("python",)).matched_skills, ())


class JobPresentationTests(unittest.TestCase):
    def test_fetched_page_keeps_precedence_when_a_later_fetch_fails(self) -> None:
        stored = job(page_title="Page title", page_description_text="Full description", page_status="failed",
                     page_fetched_at=NOW, page_valid_until=TODAY, experience_months=0, full_time=False,
                     page_work_place="Pula", page_workers_needed=0, page_experience="Nije važno")
        presenter = JobPresenter()
        card = presenter.card(stored, TODAY, None, True)
        details = presenter.details(stored, TODAY, None, [])
        comparison = presenter.comparison_input(stored, TODAY, None)
        self.assertEqual((card.title, card.deadline_source, card.deadline_passed), ("Page title", "job_page", False))
        self.assertEqual((card.workers_needed, card.conditions.experience_months, card.conditions.full_time),
                         (0, 0, False))
        self.assertEqual(card.quality_flags, ())
        self.assertEqual((details.description_text, details.description_source), ("Full description", "job_page"))
        self.assertEqual(comparison.page.experience, "Nije važno")
        self.assertEqual(comparison.conditions, card.conditions)

    def test_unread_page_preserves_unknowns_and_feed_fallbacks(self) -> None:
        presenter, stored = JobPresenter(), job()
        card = presenter.card(stored, TODAY, None, None)
        details = presenter.details(stored, TODAY, None, [])
        self.assertEqual(details.availability_status, "unknown")
        self.assertIsNone(card.conditions)
        self.assertIsNone(card.deadline_passed)
        self.assertIsNone(card.county_name)
        self.assertEqual(card.quality_flags, ("title_truncated", "deadline_unknown"))
        self.assertEqual((details.title, details.description_text, details.description_source),
                         ("Feed title", "Feed description", "feed"))
        self.assertIsNone(presenter.comparison_input(stored, TODAY, None).page)


class JobSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.jobs = [job(3), job(2), job(1)]
        self.work = SimpleNamespace(
            transaction_time=AsyncMock(return_value=NOW),
            jobs=SimpleNamespace(
                search=AsyncMock(return_value=[JobSearchHit(stored, True) for stored in self.jobs]),
                count_unknown_conditions=AsyncMock(return_value=UnknownConditionsDTO(by_filter={"full_time": 2}, total=2)),
                list_by_ids=AsyncMock(return_value=self.jobs),
                get_by_id=AsyncMock(return_value=None),
            ),
            counties=SimpleNamespace(
                get_by_code=AsyncMock(return_value=SimpleNamespace(id=5, code="istarska")),
                list_feed_checks=AsyncMock(return_value=[CountyFeedCheckDTO(
                    code="istarska", name="Istarska županija", feed_id=5, last_success_at=NOW,
                )]),
            ),
            job_feed_memberships=SimpleNamespace(list_counties=AsyncMock(return_value=[JobCountyDTO(
                job_id=stored.id, county_code="istarska", county_name="Istarska županija", presence_status="present",
            ) for stored in self.jobs])),
        )
        self.active = self.opened = 0

        @asynccontextmanager
        async def open_work():
            self.opened += 1
            self.active += 1
            try:
                yield self.work
            finally:
                self.active -= 1

        self.service = JobSearchServiceFactory(Settings(_env_file=None)).create(open_work)

    async def test_search_and_cards_share_paging_and_unknown_counts(self) -> None:
        filters = JobSearchFiltersDTO(query="kuharica", county="Istarska županija", full_time=False, limit=2)
        page = await self.service.search(filters)
        cards = await self.service.search_cards(filters)
        self.assertEqual([result.id for result in page.jobs], [3, 2])
        self.assertEqual([result.id for result in cards.jobs], [3, 2])
        self.assertEqual((page.next_cursor, page.unknown_total), (cards.next_cursor, 2))
        self.assertEqual(cards.unknown_conditions, {"full_time": 2})
        self.assertEqual(cards.today, TODAY)
        self.assertEqual(page.coverage.data_status, "fresh")
        criteria = self.work.jobs.search.call_args.args[0]
        self.assertEqual((criteria.terms, criteria.county_id, criteria.full_time, criteria.open_on, criteria.limit),
                         (("kuhar",), 5, False, TODAY, 3))
        self.assertEqual(JobCursorCodec().decode(page.next_cursor).id, 2)
        self.assertEqual((self.opened, self.active), (2, 0))

    async def test_cursor_ranking_must_match_query_before_opening_a_transaction(self) -> None:
        cursor = JobCursorCodec().encode(JobPresenter().summary(job(), TODAY, None, None))
        with self.assertRaises(InvalidJobSearchError):
            await self.service.search(JobSearchFiltersDTO(query="kuhar", cursor=cursor))
        self.assertEqual(self.opened, 0)

    async def test_skills_reach_criteria_and_both_result_types_keep_cursor_ranking(self) -> None:
        self.jobs[0].skills = ["csharp", "python", "sql"]
        self.jobs[1].skills = ["python"]
        filters = JobSearchFiltersDTO(query="programer", skills=("csharp", "python"), limit=2)
        page = await self.service.search(filters)
        cards = await self.service.search_cards(filters)
        self.assertEqual(self.work.jobs.search.call_args.args[0].skills, ("csharp", "python"))
        self.assertEqual([row.matched_skills for row in page.jobs], [("csharp", "python"), ("python",)])
        self.assertEqual([row.matched_skills for row in cards.jobs], [("csharp", "python"), ("python",)])
        self.assertEqual(JobCursorCodec.decode(page.next_cursor).skill_matches, 1)
        await self.service.search(filters.model_copy(update={"cursor": page.next_cursor}))
        self.assertEqual(self.work.jobs.search.call_args.args[0].after.skill_matches, 1)

    async def test_skill_cursor_requires_the_corresponding_filter_before_opening_a_transaction(self) -> None:
        unranked = JobPresenter().summary(job(), TODAY, None, None)
        ranked = JobPresenter().summary(job(skills=["python", "csharp"]), TODAY, None, None,
                                        ("python", "csharp"))
        for filters in (
            JobSearchFiltersDTO(skills=("python",), cursor=JobCursorCodec.encode(unranked)),
            JobSearchFiltersDTO(cursor=JobCursorCodec.encode(ranked)),
            JobSearchFiltersDTO(skills=("python",), cursor=JobCursorCodec.encode(ranked)),
        ):
            with self.subTest(filters=filters), self.assertRaises(InvalidJobSearchError):
                await self.service.search(filters)
        self.assertEqual(self.opened, 0)

    async def test_comparison_preserves_requested_order_and_unknown_conditions(self) -> None:
        compared = await self.service.compare_jobs([1, 3], JobComparisonConditionsDTO(full_time=False))
        self.assertEqual([result.id for result in compared.jobs], [1, 3])
        self.assertEqual(compared.today, TODAY)
        self.assertTrue(all(cell.verdict == "unknown" for row in compared.rows
                            if row.aspect == "working_time" for cell in row.cells))
        self.assertEqual(self.active, 0)

    async def test_missing_job_releases_its_transaction(self) -> None:
        with self.assertRaises(NotFoundError):
            await self.service.get_job(7)
        self.assertEqual((self.opened, self.active), (1, 0))

    async def test_missing_and_duplicate_comparison_ids_keep_their_errors(self) -> None:
        with self.assertRaises(InvalidJobSearchError):
            await self.service.compare_jobs([1, 1])
        self.assertEqual(self.opened, 0)
        with self.assertRaisesRegex(NotFoundError, "7, 8"):
            await self.service.compare_jobs([7, 8])
        self.assertEqual(self.active, 0)
