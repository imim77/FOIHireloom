import unittest
from datetime import UTC, datetime
from typing import get_args

from FOIHireloom.api.apps.labels import (
    CONTRACTS,
    EDUCATION_LEVELS,
    EMPLOYMENT_TAGS,
    UNKNOWN_VALUES,
    active_filters,
    coverage_note,
    plural,
    unknown_note,
)
from FOIHireloom.dao.concrete.sqla_job import UNKNOWN_CONDITIONS
from FOIHireloom.dto.job_conditions import Contract, EducationLevel, EmploymentTag
from FOIHireloom.dto.job_market import JobMarketFiltersDTO
from FOIHireloom.dto.job_search import CoverageDTO, JobSearchFiltersDTO, RegionFreshnessDTO

CHECKED = datetime(2026, 10, 30, 3, 0, tzinfo=UTC)


def labels(**filters: object) -> list[str]:
    return [chip.label for chip in active_filters(JobSearchFiltersDTO(**filters))]


def coverage(*regions: tuple[str, str], data_status: str = "stale", hours: float = 6) -> CoverageDTO:
    return CoverageDTO(
        data_status=data_status, data_as_of=None, stale_after_hours=hours, warning="English warning",
        affected_regions=tuple(RegionFreshnessDTO(code=name.casefold(), name=name, data_status=status,
                                                  last_success_at=CHECKED if status == "stale" else None)
                               for name, status in regions),
    )


class PluralTests(unittest.TestCase):
    def test_croatian_plurals_follow_the_last_digits(self) -> None:
        forms = {count: plural(count, "oglas", "oglasa", "oglasa (5+)") for count in (1, 2, 5, 11, 12, 21, 22, 25, 111)}
        self.assertEqual(forms, {1: "oglas", 2: "oglasa", 5: "oglasa (5+)", 11: "oglasa (5+)", 12: "oglasa (5+)",
                                 21: "oglas", 22: "oglasa", 25: "oglasa (5+)", 111: "oglasa (5+)"})


class ActiveFiltersTests(unittest.TestCase):
    def test_every_value_of_every_condition_filter_has_a_label(self) -> None:
        self.assertEqual(set(CONTRACTS), set(get_args(Contract.__value__)))
        self.assertEqual(set(EDUCATION_LEVELS), set(get_args(EducationLevel.__value__)))
        self.assertEqual(list(EMPLOYMENT_TAGS), list(get_args(EmploymentTag.__value__)))
        for contract in CONTRACTS:
            with self.subTest(contract=contract):
                self.assertEqual(labels(contract=contract), [CONTRACTS[contract]])
        self.assertEqual(labels(education="secondary_4"), ["obrazovanje: srednja škola (4 god.)"])
        self.assertEqual([labels(full_time=value) for value in (True, False)],
                         [["puno radno vrijeme"], ["nepuno radno vrijeme"]])
        self.assertEqual([labels(accommodation=value) for value in (True, False)],
                         [["uz smještaj"], ["bez smještaja"]])

    def test_experience_in_months_or_whole_years(self) -> None:
        cases = {0: "bez iskustva", 6: "iskustvo do 6 mj.", 18: "iskustvo do 18 mj.", 12: "iskustvo do 1 godine",
                 24: "iskustvo do 2 godine", 60: "iskustvo do 5 godina", 132: "iskustvo do 11 godina",
                 252: "iskustvo do 21 godine", 264: "iskustvo do 22 godine"}
        for months, label in cases.items():
            with self.subTest(months=months):
                self.assertEqual(labels(max_experience_months=months), [label])

    def test_labels_follow_the_arguments_and_leave_out_the_query_and_the_page(self) -> None:
        chips = active_filters(JobSearchFiltersDTO(
            query="kuhar", county=" istarska ", category="UGOSTITELJI", max_experience_months=0, contract="permanent",
            full_time=True, education="college", accommodation=False, employment_tags=("trainee", "seasonal"),
            place=" Pula ", include_expired=True, limit=3, cursor="abc",
        ))
        self.assertEqual([(chip.argument, chip.label) for chip in chips], [
            ("county", "Istarska županija"), ("category", "kategorija UGOSTITELJI"),
            ("max_experience_months", "bez iskustva"), ("contract", "na neodređeno"),
            ("full_time", "puno radno vrijeme"), ("education", "obrazovanje: viša škola ili prvostupnik"),
            ("accommodation", "bez smještaja"),
            # Tags keep their fixed order.
            ("employment_tags", "vrsta zaposlenja: sezonski posao i pripravnik"),
            ("place", "mjesto rada Pula"), ("include_expired", "uključujući istekle oglase"),
        ])
        self.assertEqual(labels(employment_tags=("new_position", "vacancy", "retirees")),
                         ["vrsta zaposlenja: novootvoreno radno mjesto, upražnjeno radno mjesto i "
                          "zapošljavanje umirovljenika"])

    def test_county_is_named_by_its_code_or_name(self) -> None:
        self.assertEqual(labels(county="grad-zagreb"), ["Grad Zagreb"])
        self.assertEqual(labels(county="Međimurska županija"), ["Međimurska županija"])
        self.assertEqual(labels(county="nepoznata"), ["županija nepoznata"])

    def test_unset_and_blank_filters_have_no_label(self) -> None:
        self.assertEqual(labels(), [])
        self.assertEqual(labels(query="kuhar", county=" ", category="", place="  ", employment_tags=()), [])
        # The chart's filters have no county or page but are labelled the same.
        self.assertEqual([chip.label for chip in active_filters(JobMarketFiltersDTO(full_time=False, top=3))],
                         ["nepuno radno vrijeme"])


class UnknownNoteTests(unittest.TestCase):
    def test_names_every_filter_count_unknown_conditions_can_report(self) -> None:
        self.assertEqual(set(UNKNOWN_VALUES), set(UNKNOWN_CONDITIONS))

    def test_counts_the_jobs_and_names_the_unknown_values_most_often_unknown_first(self) -> None:
        note = unknown_note({"full_time": 27, "contract": 27, "max_experience_months": 30, "place": 0}, 30)
        # Ties keep the order of the filters; a filter with no unknown values is left out.
        self.assertEqual(note, "Još 30 oglasa možda odgovara, ali im nije poznato: iskustvo (30), ugovor (27), "
                               "radno vrijeme (27).")

    def test_agrees_with_the_number_of_jobs(self) -> None:
        cases = {1: "Još 1 oglas možda odgovara, ali mu nije poznato",
                 2: "Još 2 oglasa možda odgovaraju, ali im nije poznato",
                 5: "Još 5 oglasa možda odgovara, ali im nije poznato",
                 11: "Još 11 oglasa možda odgovara, ali im nije poznato",
                 21: "Još 21 oglas možda odgovara, ali im nije poznato",
                 22: "Još 22 oglasa možda odgovaraju, ali im nije poznato",
                 1325: "Još 1.325 oglasa možda odgovara, ali im nije poznato"}
        for total, start in cases.items():
            with self.subTest(total=total):
                self.assertEqual(unknown_note({"education": total}, total), f"{start}: obrazovanje ({start.split()[1]}).")

    def test_none_without_jobs_left_out(self) -> None:
        self.assertIsNone(unknown_note({}, 0))
        self.assertIsNone(unknown_note({"contract": 0}, 0))


class CoverageNoteTests(unittest.TestCase):
    def test_none_when_every_county_is_fresh(self) -> None:
        self.assertIsNone(coverage_note(coverage(data_status="fresh")))

    def test_names_one_county_without_inflecting_it(self) -> None:
        self.assertEqual(coverage_note(coverage(("Istarska županija", "stale"))),
                         "Istarska županija: podaci su stariji od 6 sati, pa rezultat možda nije potpun.")
        self.assertEqual(coverage_note(coverage(("Grad Zagreb", "unavailable"), data_status="unavailable")),
                         "Grad Zagreb: podaci nisu dostupni, pa rezultat možda nije potpun.")
        self.assertEqual(coverage_note(coverage(("Grad Zagreb", "stale"), hours=24)),
                         "Grad Zagreb: podaci su stariji od 24 sata, pa rezultat možda nije potpun.")

    def test_counts_several_counties_and_names_the_first_few(self) -> None:
        self.assertEqual(coverage_note(coverage(("Istarska županija", "stale"), ("Grad Zagreb", "stale"))),
                         "Podaci su stariji od 6 sati za 2 županije (Istarska županija i Grad Zagreb), pa rezultat "
                         "možda nije potpun.")
        many = [(f"Županija {letter}", "stale") for letter in "ABCDE"] + [("Grad Zagreb", "unavailable")]
        self.assertEqual(coverage_note(coverage(*many, data_status="unavailable")),
                         "Podaci su stariji od 6 sati ili nisu dostupni za 6 županija (Županija A, Županija B, "
                         "Županija C i još 3), pa rezultat možda nije potpun.")
        every = [(f"Županija {number}", "unavailable") for number in range(21)]
        self.assertIn("nisu dostupni za 21 županiju (", coverage_note(coverage(*every, data_status="unavailable")))

    def test_says_so_when_no_county_is_registered(self) -> None:
        self.assertEqual(coverage_note(coverage(data_status="unavailable")),
                         "Nijedna županija nije registrirana, pa nema podataka o oglasima.")
