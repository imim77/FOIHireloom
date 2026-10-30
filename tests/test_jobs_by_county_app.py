import hashlib
import unittest
from datetime import date

from FOIHireloom.api.apps.jobs_by_county import RESOURCE_URI, jobs_by_county, page
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

    def test_description_names_the_filters_and_the_day(self) -> None:
        self.assertEqual(jobs_by_county(stats(), 8, None, " ").description, "Aktivni oglasi na dan 30. 10. 2026.")
        self.assertEqual(jobs_by_county(stats(), 8, "kuhar", "UGOSTITELJI").description,
                         "Upit „kuhar” · kategorija UGOSTITELJI · aktivni oglasi na dan 30. 10. 2026.")

    def test_no_jobs_gives_no_counties(self) -> None:
        chart = jobs_by_county(stats(jobs=0).model_copy(update={"counties": ()}), 8, "pilot", None)
        self.assertEqual((chart.total_jobs, chart.counties), (0, ()))

    def test_page_loads_the_pinned_sdk_and_draws_3d_columns(self) -> None:
        html = page()
        self.assertIn("https://unpkg.com/@modelcontextprotocol/ext-apps@2.0.3/app-with-deps", html)
        for expected in ("app.ontoolresult", "app.onhostcontextchanged", "structuredContent", 'data-theme="dark"',
                         "prefers-reduced-motion", 'id="lit-right"', "M23.9672 0.0161L47.7527 8.05164",
                         'new Intl.NumberFormat("hr-HR"', "short_name", "workers_needed", "coverage?.warning",
                         'requestDisplayMode({ mode })', 'availableDisplayModes: ["inline", "fullscreen"]',
                         "all.slice(0, data.top)", "mask-image"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)

    def test_resource_uri_changes_with_the_page(self) -> None:
        self.assertIn(hashlib.sha256(page().encode()).hexdigest()[:12], RESOURCE_URI)
