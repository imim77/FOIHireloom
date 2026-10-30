import unittest
from datetime import date

from FOIHireloom.api.apps.jobs_by_county import jobs_by_county, page
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
    def test_keeps_the_top_counties_with_their_share_of_all_jobs(self) -> None:
        chart = jobs_by_county(stats(), 2, None, None)
        self.assertEqual((chart.total_jobs, chart.total_workers_needed, chart.counties_total), (3000, 4500, 3))
        self.assertEqual([(county.short_name, county.jobs, county.share) for county in chart.counties],
                         [("Grad Zagreb", 1325, 44.2), ("Istarska", 507, 16.9)])
        self.assertEqual(chart.counties[1].name, "Istarska županija")
        self.assertEqual(chart.coverage, FRESH)

    def test_description_names_the_filters_and_the_day(self) -> None:
        self.assertEqual(jobs_by_county(stats(), 8, None, " ").description, "Aktivni oglasi na dan 30. 10. 2026.")
        self.assertEqual(jobs_by_county(stats(), 8, "kuhar", "UGOSTITELJI").description,
                         "Upit „kuhar” · kategorija UGOSTITELJI · aktivni oglasi na dan 30. 10. 2026.")

    def test_no_jobs_gives_no_counties(self) -> None:
        chart = jobs_by_county(stats(jobs=0).model_copy(update={"counties": ()}), 8, "pilot", None)
        self.assertEqual((chart.total_jobs, chart.counties_total, chart.counties), (0, 0, ()))

    def test_page_loads_the_pinned_sdk(self) -> None:
        html = page()
        self.assertIn("https://unpkg.com/@modelcontextprotocol/ext-apps@2.0.3/app-with-deps", html)
        self.assertIn("ontoolresult", html)
