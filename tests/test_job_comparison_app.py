import unittest
from datetime import date, timedelta
from typing import get_args

from FOIHireloom.api.apps.job_comparison import UNKNOWN_REASONS, job_comparison
from FOIHireloom.api.apps.views import JOB_COMPARISON
from FOIHireloom.dto.job_comparison import (
    ComparedJobDTO,
    ComparisonCellDTO,
    ComparisonRowDTO,
    JobComparisonConditionsDTO,
    JobComparisonDTO,
    UnknownReason,
)
from FOIHireloom.dto.job_conditions import JobConditionsDTO

TODAY = date(2026, 11, 1)


def job(job_id: int, deadline_on: date | None = None, conditions: JobConditionsDTO | None = None) -> ComparedJobDTO:
    return ComparedJobDTO(
        id=job_id, display_title=f"POSAO {job_id}", employer_name=None, county_name="Istarska županija",
        display_location="PULA", canonical_url=f"https://example.com/{job_id}", details_status="fetched",
        category=None, category_source=None, published_on=TODAY - timedelta(days=3), deadline_on=deadline_on,
        deadline_passed=None if deadline_on is None else deadline_on < TODAY, conditions=conditions,
    )


def cell(job_id: int, value: str | None = None, evidence: str | None = None, verdict: str | None = None,
         unknown_reason: UnknownReason | None = None) -> ComparisonCellDTO:
    return ComparisonCellDTO(job_id=job_id, value=value, evidence=evidence, verdict=verdict,
                             reason=None if verdict is None else "an English reason", unknown_reason=unknown_reason)


def comparison(jobs: tuple[ComparedJobDTO, ...], rows: tuple[ComparisonRowDTO, ...],
               conditions: JobComparisonConditionsDTO | None = None) -> JobComparisonDTO:
    return JobComparisonDTO(today=TODAY, jobs=jobs, rows=rows, conditions=conditions)


def deadlines(*deadline_on: date | None) -> list[str]:
    jobs = tuple(job(index, day) for index, day in enumerate(deadline_on, 1))
    row = ComparisonRowDTO(aspect="deadline", differs=True, condition=None,
                           cells=tuple(cell(item.id, value="English", evidence="English") for item in jobs))
    return [item.text for item in job_comparison(comparison(jobs, (row,))).rows[0].cells]


class JobComparisonAppTests(unittest.TestCase):
    def test_title_description_and_disclaimer(self) -> None:
        jobs = (job(1), job(2))
        view = job_comparison(comparison(jobs, ()))
        self.assertEqual((view.title, view.description, view.unknown_note), ("Usporedba oglasa", "Bez zadanih uvjeta",
                                                                              None))
        self.assertEqual(view.disclaimer,
                         "Usporedba pokazuje samo što oglasi navode, ne i hoće li vas poslodavac odabrati.")
        stated = JobComparisonConditionsDTO(max_experience_months=0, contract="permanent", full_time=False,
                                            education="secondary_3", accommodation=True)
        self.assertEqual(job_comparison(comparison(jobs, (), stated)).description,
                         "Vaši uvjeti: bez iskustva · na neodređeno · nepuno radno vrijeme · obrazovanje: srednja škola "
                         "(3 god.) · uz smještaj")
        self.assertEqual(job_comparison(comparison(jobs, (), JobComparisonConditionsDTO(
            max_experience_months=24))).description, "Vaši uvjeti: iskustvo do 2 godine")
        # Conditions without a value are none.
        self.assertEqual(job_comparison(comparison(jobs, (), JobComparisonConditionsDTO())).description,
                         "Bez zadanih uvjeta")

    def test_keeps_the_comparison_for_the_llm(self) -> None:
        compared = comparison((job(1, TODAY), job(2)), (ComparisonRowDTO(
            aspect="contract", differs=True, condition="permanent",
            cells=(cell(1, "permanent", "Na neodređeno", "match"),
                   cell(2, None, None, "unknown", "page_not_read"))),))
        view = job_comparison(compared)
        self.assertEqual(view.model_dump(include=set(JobComparisonDTO.model_fields), exclude={"rows"}),
                         compared.model_dump(exclude={"rows"}))
        self.assertEqual(view.rows[0].model_dump(include=set(ComparisonRowDTO.model_fields), exclude={"cells"}),
                         compared.rows[0].model_dump(exclude={"cells"}))
        for shown, original in zip(view.rows[0].cells, compared.rows[0].cells):
            self.assertEqual(shown.model_dump(include=set(ComparisonCellDTO.model_fields)), original.model_dump())

    def test_aspects_have_croatian_names_and_the_users_condition(self) -> None:
        rows = tuple(ComparisonRowDTO(aspect=aspect, differs=False, condition=condition, cells=(cell(1), cell(2)))
                     for aspect, condition in (("experience", 6), ("education", "college"), ("contract", "fixed_term"),
                                               ("working_time", True), ("accommodation", False), ("deadline", None)))
        view = job_comparison(comparison((job(1), job(2)), rows))
        self.assertEqual([(row.name, row.condition_label) for row in view.rows], [
            ("Iskustvo", "6 mj."), ("Obrazovanje", "viša škola ili prvostupnik"), ("Ugovor", "na određeno"),
            ("Radno vrijeme", "puno radno vrijeme"), ("Smještaj", "bez smještaja"), ("Rok prijave", None),
        ])
        labels = {}
        for aspect, condition in (("experience", 0), ("experience", 12), ("experience", 36), ("experience", 60),
                                  ("working_time", False), ("accommodation", True), ("contract", None)):
            row = ComparisonRowDTO(aspect=aspect, differs=False, condition=condition, cells=(cell(1), cell(2)))
            labels[aspect, condition] = job_comparison(comparison((job(1), job(2)), (row,))).rows[0].condition_label
        self.assertEqual(labels, {
            ("experience", 0): "bez iskustva", ("experience", 12): "1 godina", ("experience", 36): "3 godine",
            ("experience", 60): "5 godina", ("working_time", False): "nepuno radno vrijeme",
            ("accommodation", True): "uz smještaj", ("contract", None): None,
        })

    def test_cells_show_the_page_text_with_the_verdict_in_croatian(self) -> None:
        row = ComparisonRowDTO(aspect="experience", differs=True, condition=0, cells=(
            cell(1, "12 months", "1 godinu", "no_match"), cell(2, "no experience required", "Nije važno", "match"),
            cell(3, None, None, "unknown", "page_not_read")))
        shown = job_comparison(comparison((job(1), job(2), job(3)), (row,))).rows[0].cells
        self.assertEqual([(item.text, item.note, item.verdict_label) for item in shown], [
            ("1 godinu", None, "ne odgovara"), ("Nije važno", None, "odgovara"),
            ("stranica oglasa još nije pročitana", None, "nije poznato"),
        ])
        # Without a condition there is no verdict, and no label for it.
        plain = row.model_copy(update={"condition": None, "cells": tuple(
            item.model_copy(update={"verdict": None, "reason": None}) for item in row.cells)})
        self.assertEqual({item.verdict_label for item in
                          job_comparison(comparison((job(1), job(2), job(3)), (plain,))).rows[0].cells}, {None})

    def test_unknown_values_say_why_in_croatian(self) -> None:
        texts = {}
        for code in UNKNOWN_REASONS:
            row = ComparisonRowDTO(aspect="education", differs=False, condition=None,
                                   cells=(cell(1, unknown_reason=code), cell(2, unknown_reason=code)))
            texts[code] = job_comparison(comparison((job(1), job(2)), (row,))).rows[0].cells[0].text
        self.assertEqual(texts, {
            "page_not_read": "stranica oglasa još nije pročitana",
            "page_unavailable": "HZZ nije vratio stranicu oglasa",
            "page_failed": "dohvat stranice nije uspio",
            "not_stated": "oglas ne navodi",
            "unreadable": "nije prepoznato",
            "contract_not_stated": "oglas navodi vrstu zaposlenja, ali ne i ugovor",
        })
        self.assertEqual(set(UNKNOWN_REASONS), set(get_args(UnknownReason.__value__)))
        # With the page's own words, the reason goes under them.
        row = ComparisonRowDTO(aspect="contract", differs=True, condition="permanent", cells=(
            cell(1, None, "Novootvoreni poslovi", "unknown", "contract_not_stated"),
            cell(2, None, "Po dogovoru", None, "unreadable")))
        shown = job_comparison(comparison((job(1), job(2)), (row,))).rows[0].cells
        self.assertEqual([(item.text, item.note) for item in shown], [
            ("Novootvoreni poslovi", "oglas navodi vrstu zaposlenja, ali ne i ugovor"),
            ("Po dogovoru", "nije prepoznato"),
        ])

    def test_known_values_without_page_text_are_worded_in_croatian(self) -> None:
        conditions = JobConditionsDTO(experience_months=0, trainee=True, education_levels=("secondary_4", "college"),
                                      contract="other", full_time=False, weekly_hours=20, accommodation="family")
        jobs = (job(1, conditions=conditions), job(2, conditions=JobConditionsDTO(experience_months=18)))
        rows = tuple(ComparisonRowDTO(aspect=aspect, differs=True, condition=None,
                                      cells=(cell(1, "English"), cell(2, "English")))
                     for aspect in ("experience", "education", "contract", "working_time", "accommodation"))
        view = job_comparison(comparison(jobs, rows))
        self.assertEqual([row.cells[0].text for row in view.rows], [
            "pripravnik", "srednja škola (4 god.) ili viša škola ili prvostupnik", "drugi oblici rada",
            "nepuno radno vrijeme, 20 h tjedno", "obiteljski stan",
        ])
        self.assertEqual(view.rows[0].cells[1].text, "18 mj.")

    def test_deadlines_count_the_days_left_with_croatian_plurals(self) -> None:
        self.assertEqual(deadlines(TODAY + timedelta(days=28), TODAY, TODAY - timedelta(days=1), None), [
            "do 29. 11. 2026. (još 28 dana)", "do 01. 11. 2026. (zadnji dan)", "istekao 31. 10. 2026.", "nije naveden",
        ])
        self.assertEqual(deadlines(*(TODAY + timedelta(days=days) for days in (1, 2, 5))), [
            "do 02. 11. 2026. (još 1 dan)", "do 03. 11. 2026. (još 2 dana)", "do 06. 11. 2026. (još 5 dana)",
        ])
        self.assertEqual(deadlines(*(TODAY + timedelta(days=days) for days in (11, 21, 24))), [
            "do 12. 11. 2026. (još 11 dana)", "do 22. 11. 2026. (još 21 dan)", "do 25. 11. 2026. (još 24 dana)",
        ])

    def test_unknown_note_counts_the_unknown_verdicts(self) -> None:
        def note(*verdicts: tuple[str | None, ...]) -> str | None:
            rows = tuple(ComparisonRowDTO(aspect="experience", differs=False, condition=0, cells=tuple(
                cell(index, verdict=verdict, unknown_reason="not_stated" if verdict == "unknown" else None)
                for index, verdict in enumerate(row, 1))) for row in verdicts)
            return job_comparison(comparison((job(1), job(2)), rows)).unknown_note

        self.assertIsNone(note(("match", "no_match")))
        self.assertEqual(note(("unknown", "match")),
                         "Za 1 uvjet podatak u oglasu nije poznat; to ne znači da je ispunjen.")
        self.assertEqual(note(("unknown", "match"), ("unknown", "no_match")),
                         "Za 2 uvjeta podatak u oglasu nije poznat; to ne znači da su ispunjeni.")
        self.assertEqual(note(*[("unknown", "unknown")] * 3),
                         "Za 6 uvjeta podatak u oglasima nije poznat; to ne znači da su ispunjeni.")
        self.assertEqual(note(*[("unknown", "unknown")] * 10, ("unknown", "match")),
                         "Za 21 uvjet podatak u oglasima nije poznat; to ne znači da je ispunjen.")

    def test_built_page_shows_the_table_the_verdicts_and_the_notes(self) -> None:
        html = JOB_COMPARISON.page()
        for expected in ("Usporedba oglasa", "razlikuje se", "vi: ",
                         "Otvori oglas na HZZ-u", "Skupina zanimanja dopunjena iz HZZ-ova feeda po zanimanju",
                         ".verdict.no_match{", "position:sticky", ".note{"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)
