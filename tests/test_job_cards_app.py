import unittest
from datetime import UTC, date, datetime

from FOIHireloom.api.apps.job_cards import job_cards
from FOIHireloom.api.apps.views import JOB_CARDS
from FOIHireloom.dto.job_search import (
    ActiveFilterDTO,
    CoverageDTO,
    JobCardDTO,
    JobCardsPageDTO,
    JobSearchFiltersDTO,
    RegionFreshnessDTO,
)

FRESH = CoverageDTO(data_status="fresh", data_as_of=None, stale_after_hours=6, affected_regions=(), warning=None)
CARD = JobCardDTO(
    id=7, source_job_id="7", title="KUHAR/KUHARICA", category=None, location_text=None, municipality=None,
    published_on=date(2026, 10, 29), deadline_on=date(2026, 11, 12), canonical_url="https://example.com/7",
    quality_flags=(), last_seen_at=datetime(2026, 10, 30, tzinfo=UTC), workers_needed=3,
    accommodation="Zajednički smještaj",
)
PAGE = JobCardsPageDTO(jobs=(CARD,), next_cursor="next", coverage=FRESH, today=date(2026, 10, 30))


class JobCardsAppTests(unittest.TestCase):
    def test_title_names_the_query_and_description_the_day_while_the_filters_become_chips(self) -> None:
        cards = job_cards(PAGE, JobSearchFiltersDTO(query=" kuhar ", county="istarska", category="UGOSTITELJI"))
        self.assertEqual((cards.title, cards.description), ("Oglasi za „kuhar”", "Aktivni oglasi na dan 30. 10. 2026."))
        self.assertEqual(cards.active_filters, (ActiveFilterDTO(argument="county", label="županija istarska"),
                                                ActiveFilterDTO(argument="category", label="kategorija UGOSTITELJI")))
        newest = job_cards(PAGE, JobSearchFiltersDTO(include_expired=True))
        self.assertEqual((newest.title, newest.description), ("Najnoviji oglasi", "Svi oglasi na dan 30. 10. 2026."))
        self.assertEqual([chip.argument for chip in newest.active_filters], ["include_expired"])

    def test_keeps_the_page_and_the_filters_for_the_next_page(self) -> None:
        conditions = dict(max_experience_months=0, contract="permanent", full_time=True, education="secondary_3",
                          accommodation=True, employment_tags=("seasonal",), place="Pula")
        page = PAGE.model_copy(update={"unknown_conditions": {"contract": 2}, "unknown_total": 2})
        cards = job_cards(page, JobSearchFiltersDTO(query="kuhar", limit=4, cursor="previous", **conditions))
        self.assertEqual((cards.jobs, cards.next_cursor, cards.coverage, cards.today), (PAGE.jobs, "next", FRESH,
                                                                                       date(2026, 10, 30)))
        self.assertEqual((cards.unknown_conditions, cards.unknown_total), ({"contract": 2}, 2))
        self.assertEqual((cards.jobs[0].workers_needed, cards.jobs[0].accommodation), (3, "Zajednički smještaj"))
        # The view passes next_cursor back with these filters, so the cursor that found this page is left out.
        self.assertEqual(cards.filters, JobSearchFiltersDTO(query="kuhar", limit=4, **conditions))
        self.assertEqual([chip.argument for chip in cards.active_filters], list(conditions))

    def test_notes_say_in_croatian_what_the_coverage_warning_and_the_unknown_counts_do(self) -> None:
        cards = job_cards(PAGE, JobSearchFiltersDTO())
        self.assertEqual((cards.coverage_note, cards.unknown_note), (None, None))
        stale = FRESH.model_copy(update={"data_status": "stale", "warning": "Job data for the requested county …",
                                         "affected_regions": (RegionFreshnessDTO(
                                             code="istarska", name="Istarska županija", data_status="stale",
                                             last_success_at=datetime(2026, 10, 30, tzinfo=UTC)),)})
        page = PAGE.model_copy(update={"coverage": stale, "unknown_conditions": {"contract": 2}, "unknown_total": 2})
        cards = job_cards(page, JobSearchFiltersDTO(contract="permanent"))
        self.assertEqual(cards.coverage_note,
                         "Istarska županija: podaci su stariji od 6 sati, pa rezultat možda nije potpun.")
        self.assertEqual(cards.unknown_note, "Još 2 oglasa možda odgovaraju, ali im nije poznato: ugovor (2).")
        # The LLM still gets the service's warning.
        self.assertEqual(cards.coverage.warning, "Job data for the requested county …")

    def test_built_page_shows_the_filters_the_notes_and_the_normalised_conditions(self) -> None:
        html = JOB_CARDS.page()
        for expected in ("Ukloni filtar", "show_jobs", "Skupina zanimanja dopunjena iz HZZ-ova feeda po zanimanju",
                         "Za pripravnike", "h tjedno", "Na neodređeno", "Obiteljski stan", ".note{"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)
