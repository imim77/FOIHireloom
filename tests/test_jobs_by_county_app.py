import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from FOIHireloom.api.apps.jobs_by_county import jobs_by_county
from FOIHireloom.api.apps.views import BUILD_HINT, JOBS_BY_COUNTY, AppView, stale_sources
from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO
from FOIHireloom.dto.job_search import CoverageDTO

FRESH = CoverageDTO(data_status="fresh", data_as_of=None, stale_after_hours=6, affected_regions=(), warning=None)
ALL = JobMarketFiltersDTO()
NO_BREAKDOWNS = dict.fromkeys(("categories", "employers", "contracts", "employment_tags", "working_time",
                               "experience_bands", "education_levels", "accommodation", "schedule_tags",
                               "transport_allowance"), ())


def stats(jobs: int = 3000, counties: tuple = ()) -> JobMarketStatsDTO:
    return JobMarketStatsDTO(
        jobs=jobs, with_details=jobs, with_category=0, category_from_description=0, category_from_feed=0,
        workers_needed=4500, published_recently=0, closing_soon=0,
        counties=counties or (
            {"code": "grad-zagreb", "name": "Grad Zagreb", "jobs": 1325, "workers_needed": 3093},
            {"code": "istarska", "name": "Istarska županija", "jobs": 507, "workers_needed": 1185},
            {"code": "licko-senjska", "name": "Ličko-senjska županija", "jobs": 1, "workers_needed": 2},
        ),
        **NO_BREAKDOWNS, today=date(2026, 10, 30), coverage=FRESH, unknown_conditions={"full_time": 4},
        unknown_total=4,
    )


class JobsByCountyAppTests(unittest.TestCase):
    def test_returns_every_county_with_its_share_and_how_many_to_show_first(self) -> None:
        chart = jobs_by_county(stats(), 2, ALL)
        self.assertEqual((chart.total_jobs, chart.total_workers_needed, chart.top), (3000, 4500, 2))
        self.assertEqual([(county.short_name, county.jobs, county.share) for county in chart.counties],
                         [("Grad Zagreb", 1325, 44.2), ("Istarska", 507, 16.9), ("Ličko-senjska", 1, 0.0)])
        self.assertEqual(chart.counties[1].name, "Istarska županija")
        self.assertEqual((chart.coverage, chart.unknown_conditions, chart.unknown_total), (FRESH, {"full_time": 4}, 4))

    def test_ranks_and_titles_the_counties_by_the_chosen_metric(self) -> None:
        by_jobs = jobs_by_county(stats(), 7, ALL)
        self.assertEqual((by_jobs.metric, by_jobs.title), ("jobs", "Broj oglasa po županijama"))
        stats_ = stats(counties=(
            {"code": "a", "name": "Alfa", "jobs": 10, "workers_needed": 10},
            {"code": "b", "name": "Beta", "jobs": 5, "workers_needed": 40},
            {"code": "c", "name": "Ceta", "jobs": 5, "workers_needed": 10},
        ))
        by_workers = jobs_by_county(stats_, 7, ALL, "workers_needed")
        self.assertEqual((by_workers.metric, by_workers.title),
                         ("workers_needed", "Broj traženih radnika po županijama"))
        self.assertEqual([county.code for county in by_workers.counties], ["b", "a", "c"])
        # Ties keep name order.
        self.assertEqual([county.code for county in jobs_by_county(stats_, 7, ALL).counties], ["a", "b", "c"])

    def test_description_names_the_query_the_filters_and_the_day(self) -> None:
        self.assertEqual(jobs_by_county(stats(), 8, JobMarketFiltersDTO(category=" ")).description,
                         "Aktivni oglasi na dan 30. 10. 2026.")
        filters = JobMarketFiltersDTO(query="kuhar", category="UGOSTITELJI", full_time=True, include_expired=True)
        chart = jobs_by_county(stats(), 8, filters)
        # The day says that expired jobs count, so the description does not name that filter again.
        self.assertEqual(chart.description,
                         "Upit „kuhar” · kategorija UGOSTITELJI · puno radno vrijeme · svi oglasi na dan 30. 10. 2026.")
        self.assertEqual([chip.argument for chip in chart.active_filters], ["category", "full_time", "include_expired"])

    def test_notes_say_in_croatian_what_the_coverage_warning_and_the_unknown_counts_do(self) -> None:
        chart = jobs_by_county(stats(), 8, JobMarketFiltersDTO(full_time=True))
        self.assertEqual((chart.coverage_note, chart.unknown_note),
                         (None, "Još 4 oglasa možda odgovaraju, ali im nije poznato: radno vrijeme (4)."))
        empty = stats().model_copy(update={"coverage": FRESH.model_copy(update={"data_status": "unavailable"}),
                                           "unknown_conditions": {}, "unknown_total": 0})
        chart = jobs_by_county(empty, 8, ALL)
        self.assertEqual((chart.coverage_note, chart.unknown_note),
                         ("Nijedna županija nije registrirana, pa nema podataka o oglasima.", None))

    def test_no_jobs_gives_no_counties(self) -> None:
        chart = jobs_by_county(stats(jobs=0).model_copy(update={"counties": ()}), 8, JobMarketFiltersDTO(query="pilot"))
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


class BuiltPagesTests(unittest.TestCase):
    def test_pages_are_built_from_the_current_frontend(self) -> None:
        stale = stale_sources()
        self.assertEqual(stale, [], f"frontend/dist/ is older than these sources; {BUILD_HINT}.")

    def test_stale_sources_names_each_file_added_removed_or_changed_since_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frontend = Path(directory)
            (frontend / "src" / "views").mkdir(parents=True)
            (frontend / "src" / "views" / "a.tsx").write_text("a")
            (frontend / "src" / "b.ts").write_text("b")
            (frontend / "package.json").write_text("{}")
            self.assertEqual(stale_sources(frontend), ["dist/sources.json"])

            files = {path: hashlib.sha256((frontend / path).read_bytes()).hexdigest()
                     for path in ("src/views/a.tsx", "src/b.ts", "package.json")}
            (frontend / "dist").mkdir()
            (frontend / "dist" / "sources.json").write_text(
                json.dumps({"sources": ["src", "package.json"], "files": files}))
            # Dotfiles such as .DS_Store do not count.
            (frontend / "src" / ".DS_Store").write_text("x")
            self.assertEqual(stale_sources(frontend), [])

            (frontend / "src" / "views" / "a.tsx").write_text("a2")
            (frontend / "src" / "c.ts").write_text("c")
            (frontend / "package.json").unlink()
            self.assertEqual(stale_sources(frontend), ["package.json", "src/c.ts", "src/views/a.tsx"])
