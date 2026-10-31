import unittest
from datetime import UTC, date, datetime

from FOIHireloom.api.apps.job_cards import job_cards
from FOIHireloom.dto.job_search import CoverageDTO, JobCardDTO, JobCardsPageDTO, JobSearchFiltersDTO

FRESH = CoverageDTO(data_status="fresh", data_as_of=None, stale_after_hours=6, affected_regions=(), warning=None)
CARD = JobCardDTO(
    id=7, source_job_id="7", title="KUHAR/KUHARICA", category=None, location_text=None, municipality=None,
    published_on=date(2026, 10, 29), deadline_on=date(2026, 11, 12), canonical_url="https://example.com/7",
    quality_flags=(), last_seen_at=datetime(2026, 10, 30, tzinfo=UTC), workers_needed=3,
    accommodation="Zajednički smještaj",
)
PAGE = JobCardsPageDTO(jobs=(CARD,), next_cursor="next", coverage=FRESH, today=date(2026, 10, 30))


class JobCardsAppTests(unittest.TestCase):
    def test_title_and_description_name_the_query_filters_and_day(self) -> None:
        cards = job_cards(PAGE, JobSearchFiltersDTO(query=" kuhar ", county="istarska", category="UGOSTITELJI"))
        self.assertEqual(cards.title, "Oglasi za „kuhar”")
        self.assertEqual(cards.description,
                         "Županija istarska · kategorija UGOSTITELJI · aktivni oglasi na dan 30. 10. 2026.")
        newest = job_cards(PAGE, JobSearchFiltersDTO(include_expired=True))
        self.assertEqual((newest.title, newest.description), ("Najnoviji oglasi", "Svi oglasi na dan 30. 10. 2026."))

    def test_keeps_the_page_and_the_filters_for_the_next_page(self) -> None:
        conditions = dict(max_experience_months=0, contract="permanent", full_time=True, education="secondary_3",
                          accommodation=True, employment_tags=("seasonal",), place="Pula")
        page = PAGE.model_copy(update={"unknown_conditions": {"contract": 2}})
        cards = job_cards(page, JobSearchFiltersDTO(query="kuhar", limit=4, cursor="previous", **conditions))
        self.assertEqual((cards.jobs, cards.next_cursor, cards.coverage, cards.today, cards.unknown_conditions),
                         (PAGE.jobs, "next", FRESH, date(2026, 10, 30), {"contract": 2}))
        self.assertEqual((cards.jobs[0].workers_needed, cards.jobs[0].accommodation), (3, "Zajednički smještaj"))
        # The view passes next_cursor back with these filters, so the cursor that found this page is left out.
        self.assertEqual(cards.filters, JobSearchFiltersDTO(query="kuhar", limit=4, **conditions))
