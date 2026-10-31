import hashlib
import unittest
from datetime import date

from FOIHireloom.api.apps.jobs_by_county import jobs_by_county
from FOIHireloom.api.apps.views import JOBS_BY_COUNTY, AppView
from FOIHireloom.dto.job_market import JobMarketStatsDTO
from FOIHireloom.dto.job_search import CoverageDTO

FRESH = CoverageDTO(data_status="fresh", data_as_of=None, stale_after_hours=6, affected_regions=(), warning=None)


def stats(jobs: int = 3000, counties: tuple = ()) -> JobMarketStatsDTO:
    return JobMarketStatsDTO(
        jobs=jobs, with_details=jobs, with_category=0, workers_needed=4500, published_recently=0, closing_soon=0,
        counties=counties or (
            {"code": "grad-zagreb", "name": "Grad Zagreb", "jobs": 1325, "workers_needed": 3093},
            {"code": "istarska", "name": "Istarska županija", "jobs": 507, "workers_needed": 1185},
            {"code": "licko-senjska", "name": "Ličko-senjska županija", "jobs": 1, "workers_needed": 2},
        ),
        categories=(), employers=(), employment_types=(), working_hours=(), education=(), experience=(),
        accommodation=(), today=date(2026, 10, 30), coverage=FRESH,
    )


class JobsByCountyAppTests(unittest.TestCase):
    def test_returns_every_county_with_its_share_and_how_many_to_show_first(self) -> None:
        chart = jobs_by_county(stats(), 2, None, None)
        self.assertEqual((chart.total_jobs, chart.total_workers_needed, chart.top), (3000, 4500, 2))
        self.assertEqual([(county.short_name, county.jobs, county.share) for county in chart.counties],
                         [("Grad Zagreb", 1325, 44.2), ("Istarska", 507, 16.9), ("Ličko-senjska", 1, 0.0)])
        self.assertEqual(chart.counties[1].name, "Istarska županija")
        self.assertEqual(chart.coverage, FRESH)

    def test_ranks_and_titles_the_counties_by_the_chosen_metric(self) -> None:
        by_jobs = jobs_by_county(stats(), 7, None, None)
        self.assertEqual((by_jobs.metric, by_jobs.title), ("jobs", "Broj oglasa po županijama"))
        stats_ = stats(counties=(
            {"code": "a", "name": "Alfa", "jobs": 10, "workers_needed": 10},
            {"code": "b", "name": "Beta", "jobs": 5, "workers_needed": 40},
            {"code": "c", "name": "Ceta", "jobs": 5, "workers_needed": 10},
        ))
        by_workers = jobs_by_county(stats_, 7, None, None, "workers_needed")
        self.assertEqual((by_workers.metric, by_workers.title),
                         ("workers_needed", "Broj traženih radnika po županijama"))
        self.assertEqual([county.code for county in by_workers.counties], ["b", "a", "c"])
        # Ties keep name order.
        self.assertEqual([county.code for county in jobs_by_county(stats_, 7, None, None).counties], ["a", "b", "c"])

    def test_description_names_the_filters_and_the_day(self) -> None:
        self.assertEqual(jobs_by_county(stats(), 8, None, " ").description, "Aktivni oglasi na dan 30. 10. 2026.")
        self.assertEqual(jobs_by_county(stats(), 8, "kuhar", "UGOSTITELJI").description,
                         "Upit „kuhar” · kategorija UGOSTITELJI · aktivni oglasi na dan 30. 10. 2026.")

    def test_no_jobs_gives_no_counties(self) -> None:
        chart = jobs_by_county(stats(jobs=0).model_copy(update={"counties": ()}), 8, "pilot", None)
        self.assertEqual((chart.total_jobs, chart.counties), (0, ()))

    def test_built_page_inlines_the_sdk_and_draws_3d_columns(self) -> None:
        html = JOBS_BY_COUNTY.page()
        self.assertTrue(html.startswith("<!doctype html>"))
        # Built by frontend/ into one file: nothing loads from the web.
        for absent in ("unpkg", 'src="http', "<link"):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, html)
        for expected in ("ui/initialize", "ui/notifications/tool-result", "ui/request-display-mode",
                         "data-theme=dark", "prefers-reduced-motion", "M23.9672 0.0161L47.7527 8.05164", "hr-HR",
                         "traženih radnika", "Nema aktivnih oglasa za zadane filtre.", "Graf se nije mogao prikazati"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)

    def test_resource_uri_changes_with_the_page(self) -> None:
        self.assertEqual(JOBS_BY_COUNTY.uri,
                         f"ui://foihireloom/jobs-by-county-{hashlib.sha256(JOBS_BY_COUNTY.page().encode()).hexdigest()[:12]}.html")

    def test_a_page_that_was_not_built_says_how_to_build_it(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "npm run build"):
            AppView("missing", "").page()
