import unittest
from collections import Counter
from datetime import date
from decimal import Decimal

from dzs_workbooks import CROATIA, DzsFiles, save

from FOIHireloom.dto.dzs import DzsReleaseDTO, DzsValueDTO
from FOIHireloom.exceptions import DzsValidationError
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.dzs_release_parser import DzsReleaseParser


class DzsReleaseParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = DzsFiles()
        self.parser = DzsReleaseParser(CroatianCountyCatalog())

    def parse(self) -> DzsReleaseDTO:
        return self.parser.parse(self.files.t1_bytes(), self.files.workbook_bytes())

    def problems(self, t1: bytes | None = None, workbook: bytes | None = None) -> tuple[str, ...]:
        with self.assertRaises(DzsValidationError) as error:
            self.parser.parse(t1 or self.files.t1_bytes(), workbook or self.files.workbook_bytes())
        return error.exception.problems

    def assert_problem(self, expected: str, **files: bytes) -> tuple[str, ...]:
        problems = self.problems(**files)
        self.assertTrue(any(expected in problem for problem in problems), problems)
        return problems

    def values(self, release: DzsReleaseDTO) -> dict[tuple, DzsValueDTO]:
        return {value.key: value for value in release.values}

    def test_release_keeps_t1_for_shared_keys_and_the_workbook_series_for_the_rest(self) -> None:
        release = self.parse()
        counts = Counter(value.source for value in release.values)
        self.assertEqual(counts, {"t1": 504, "workbook_9_4_13": 21 * 2 * 8, "workbook_9_4_14": 21 * (3 * 11 - 2 * 3)})
        self.assertEqual(len(release.values), len({value.key for value in release.values}))
        self.assertNotIn(None, {value.county_iso for value in release.values})
        values = self.values(release)
        september = date(2026, 9, 1)
        unemployed = values[("HR-05", "unemployed", september, "total")]
        self.assertEqual((unemployed.value, unemployed.is_provisional, unemployed.source),
                         (Decimal(self.files.get_t1("Varaždinska", "total", "unemployed", 9)), False, "t1"))
        rate = values[("HR-05", "unemployment_rate", september, "women")]
        self.assertEqual((rate.source, rate.is_provisional), ("t1", True))
        self.assertEqual(rate.value.as_tuple().exponent, -1)
        men = values[("HR-05", "unemployment_rate", september, "men")]
        self.assertEqual((men.source, men.is_provisional), ("workbook_9_4_14", True))
        self.assertNotIn(("HR-05", "unemployed", september, "men"), values)
        self.assertNotIn(("HR-05", "active_population", september, "men"), values)
        self.assertFalse(values[("HR-05", "active_population", date(2025, 12, 1), "total")].is_provisional)
        self.assertTrue(values[("HR-05", "active_population", date(2026, 1, 1), "women")].is_provisional)
        self.assertEqual(min(value.period for value in release.values), date(2025, 11, 1))
        self.assertEqual(
            [(s.source, s.values, s.first_period, s.last_period) for s in release.series],
            [("t1", 504, date(2026, 7, 1), september),
             ("workbook_9_4_13", 336, date(2025, 11, 1), date(2026, 6, 1)),
             ("workbook_9_4_14", 567, date(2025, 11, 1), september)],
        )
        self.assertEqual([s.provisional for s in release.series], [378, 21 * 2 * 6, 21 * (3 * 9 - 6)])

    def test_markers_and_empty_cells_are_missing_values_and_zero_is_a_value(self) -> None:
        for month, value in ((11, "-"), (12, "…"), (1, None), (2, " "), (3, 0), (4, "..."), (5, " - ")):
            self.files.set_series("9.4.14.", "Istarska", 2025 + (month < 7), month, "men", value)
        self.files.set_t1("Istarska", "women", "unemployed", 7, "-")
        self.files.set_t1("Istarska", "women", "unemployment_rate", 7, "-")
        self.files.set_series("9.4.14.", "Istarska", 2026, 7, "women", "-")
        values = self.values(self.parse())

        def stored(year: int, month: int, sex: str = "men", indicator: str = "unemployment_rate") -> tuple:
            value = values[("HR-18", indicator, date(year, month, 1), sex)]
            return value.value, value.missing_reason

        self.assertEqual(stored(2025, 11), (None, "no_occurrence"))
        self.assertEqual(stored(2025, 12), (None, "not_available"))
        self.assertEqual(stored(2026, 1), (None, "empty"))
        self.assertEqual(stored(2026, 2), (None, "empty"))
        self.assertEqual(stored(2026, 3), (Decimal("0.0"), None))
        self.assertEqual(stored(2026, 4), (None, "not_available"))
        self.assertEqual(stored(2026, 5), (None, "no_occurrence"))
        self.assertEqual(stored(2026, 7, "women"), (None, "no_occurrence"))
        self.assertEqual(stored(2026, 7, "women", "unemployed"), (None, "no_occurrence"))
        self.assertEqual([s.missing for s in self.parse().series], [2, 0, 6])

    def test_rates_accept_int_and_float_cells_with_one_decimal(self) -> None:
        self.files.set_t1("Zadarska", "total", "unemployment_rate", 8, 4)
        self.files.set_series("9.4.14.", "Zadarska", 2026, 8, "total", 4.0)
        self.files.set_series("9.4.14.", "Zadarska", 2026, 1, "men", 12)
        values = self.values(self.parse())
        self.assertEqual(str(values[("HR-13", "unemployment_rate", date(2026, 8, 1), "total")].value), "4.0")
        self.assertEqual(str(values[("HR-13", "unemployment_rate", date(2026, 1, 1), "men")].value), "12.0")
        for bad in (2.35, 100.1, -0.1):
            with self.subTest(rate=bad):
                self.files.set_series("9.4.14.", "Zadarska", 2026, 1, "men", bad)
                self.assert_problem(f"9.4.14.!M20: rate {bad!r} is not a percentage with one decimal.")

    def test_persons_must_be_whole_non_negative_numbers(self) -> None:
        self.files.set_series("9.4.13.", "Zadarska", 2026, 1, "total", 64036.0)
        self.assertEqual(self.values(self.parse())[("HR-13", "active_population", date(2026, 1, 1), "total")].value,
                         Decimal(64036))
        for bad, message in ((64036.5, "not a whole number"), (-1, "not a whole number"), ("n/a", "neither a number"),
                             (True, "is not a number"), (date(2026, 1, 1), "is not a number")):
            with self.subTest(value=bad):
                self.files.set_series("9.4.13.", "Zadarska", 2026, 1, "total", bad)
                self.assert_problem(message)

    def test_whitespace_in_labels_headers_and_titles_is_normalised(self) -> None:
        rows = self.files.sheets["9.4.13."]
        rows[self.files.series_cell("9.4.13.", "Međimurska", 2026, 1, "total")[0]][0] = "Međimurska "
        city = self.files.t1_cell("Grad Zagreb", "total", "employed", 7)[0]
        self.files.t1[city][0] = "  Grad\nZagreb "
        self.files.t1[city + 1][0] = "Žene "
        header = self.files.t1_cell(CROATIA, "total", "employed", 7)[0] - 2
        self.files.t1[header][1] = " Aktivno  stanovništvo1) "
        self.files.t1[1][0] = "1.  AKTIVNO STANOVNIŠTVO ADMINISTRATIVNIM IZVORIMA PO ŽUPANIJAMA I PREMA SPOLU U 2026. "
        values = self.values(self.parse())
        self.assertIn(("HR-20", "active_population", date(2026, 1, 1), "total"), values)
        self.assertIn(("HR-21", "employed", date(2026, 7, 1), "women"), values)

    def test_unknown_duplicate_or_missing_counties_reject_the_files(self) -> None:
        row = self.files.series_cell("9.4.14.", "Zagrebačka", 2026, 1, "total")[0]
        self.files.sheets["9.4.14."][row][0] = "Zagreb"
        problems = self.assert_problem("9.4.14.!A8: unknown county label 'Zagreb'.")
        self.assertIn("9.4.14.: missing counties: Zagrebačka županija.", problems)

        self.files = DzsFiles()
        rows = self.files.sheets["9.4.13."]
        istria = self.files.series_cell("9.4.13.", "Istarska", 2026, 1, "total")[0]
        rows[istria] = list(rows[istria - 1])
        problems = self.assert_problem("9.4.13.: 2 rows for Splitsko-dalmatinska županija.")
        self.assertIn("9.4.13.: missing counties: Istarska županija.", problems)

        self.files = DzsFiles()
        croatia = self.files.t1_cell(CROATIA, "total", "employed", 7)[0]
        del self.files.t1[croatia:croatia + 2]
        self.assert_problem("T1: no 'Republika Hrvatska' row.")

    def test_t1_rows_must_pair_each_area_with_its_women_row(self) -> None:
        row = self.files.t1_cell("Karlovačka", "women", "employed", 7)[0]
        del self.files.t1[row]
        self.assert_problem("no 'Žene' row after 'Karlovačka'.")

    def test_wrong_titles_headers_and_sheets_reject_the_files(self) -> None:
        cases = [
            (lambda f: f.t1.__setitem__(1, ["1. AKTIVNO STANOVNIŠTVO PO ŽUPANIJAMA"]), "T1: title '1. AKTIVNO"),
            (lambda f: f.t1[3].__setitem__(7, "Registrirani nezaposleni"), "T1!A4: expected column groups"),
            (lambda f: f.t1[4].__setitem__(5, "13."), "expected a Roman month"),
            (lambda f: f.t1[4].__setitem__(1, "VI."), "must cover the same consecutive months"),
            (lambda f: f.sheets["9.4.13."].__setitem__(1, ["AKTIVNO STANOVNIŠTVO"]), "9.4.13.: title"),
            (lambda f: f.sheets["9.4.14."][5].__setitem__(1, None), "expected 'County of'"),
            (lambda f: f.sheets["9.4.14."][5].__setitem__(8, "XI. 2025. ukupno Men"), "unexpected column header"),
            (lambda f: f.sheets["9.4.14."][5].__setitem__(8, "XIII. 2025. ukupno Total"), "unexpected column header"),
            (lambda f: f.sheets["9.4.14."][5].__setitem__(8, None), "unexpected column header ''"),
            (lambda f: f.sheets["9.4.13."][5].__setitem__(5, "XI. 2025. ukupno Total"), "second column for 2025-11 total"),
            (lambda f: [row.__delitem__(slice(6, 8)) for row in f.sheets["9.4.13."][5:28]],
             "months between 2025-11 and 2026-01 are missing"),
            (lambda f: f.sheets.pop("9.4.14."), "Workbook: missing sheet(s) 9.4.14."),
        ]
        for edit, expected in cases:
            with self.subTest(expected=expected):
                self.files = DzsFiles()
                edit(self.files)
                self.assert_problem(expected)

    def test_t1_identity_and_croatia_total_are_checked(self) -> None:
        active = self.files.get_t1("Ličko-senjska", "women", "active_population", 8)
        self.files.set_t1("Ličko-senjska", "women", "active_population", 8, active + 1)
        problems = self.assert_problem(
            f"T1: Ličko-senjska županija 2026-08 women: active population {active + 1} is not employed"
        )
        self.assertTrue(any("T1 and 9.4.13. differ for Ličko-senjska županija 2026-08 women" in p for p in problems))

        self.files = DzsFiles()
        national = self.files.get_t1(CROATIA, "total", "unemployed", 9)
        self.files.set_t1(CROATIA, "total", "unemployed", 9, national + 1)
        self.files.set_t1(CROATIA, "total", "employed", 9, self.files.get_t1(CROATIA, "total", "employed", 9) - 1)
        self.assert_problem(f"T1: unemployed in the 21 counties add up to {national}, not {national + 1} for Croatia "
                            "(2026-09 total).")

    def test_t1_and_workbook_must_agree_and_cover_the_same_months(self) -> None:
        self.files.set_series("9.4.14.", "Grad Zagreb", 2026, 9, "total", 9.9)
        self.assert_problem("T1 and 9.4.14. differ for Grad Zagreb 2026-09 total:")

        self.files = DzsFiles()
        self.files.set_series("9.4.13.", CROATIA, 2026, 7, "women", 1)
        self.assert_problem("T1 and 9.4.13. differ for Republika Hrvatska 2026-07 women:")

        self.files = DzsFiles()
        for row in self.files.sheets["9.4.14."][5:28]:
            del row[-3:]
        self.assert_problem("9.4.14.: no columns for the T1 months 2026-09.")

    def test_provisional_footnotes_are_required(self) -> None:
        cases = [
            (lambda f: f.t1.remove(["1) Privremeni podatak."]), "T1: footnote 'Privremeni podatak.' not found."),
            (lambda f: f.sheets["9.4.13."].remove(["1) Podaci od 2026. privremeni su."]),
             "9.4.13.: footnote 'Podaci od YYYY. privremeni su.' not found."),
            (lambda f: f.sheets["9.4.14."].__setitem__(1, ["STOPA REGISTRIRANE NEZAPOSLENOSTI PO ŽUPANIJAMA I PREMA SPOLU1)"]),
             "9.4.14.: the title does not refer to the provisional data footnote 2)."),
        ]
        for edit, expected in cases:
            with self.subTest(expected=expected):
                self.files = DzsFiles()
                edit(self.files)
                self.assert_problem(expected)

    def test_provisional_year_comes_from_the_footnote(self) -> None:
        self.files.sheets["9.4.13."][-3] = ["1) Podaci od 2025. privremeni su."]
        values = self.values(self.parse())
        self.assertTrue(values[("HR-05", "active_population", date(2025, 11, 1), "total")].is_provisional)
        self.assertFalse(values[("HR-05", "unemployment_rate", date(2025, 11, 1), "total")].is_provisional)

    def test_unreadable_files_and_problems_in_both_files_are_all_reported(self) -> None:
        self.assert_problem("T1 file: not an XLSX workbook.", t1=b"not a zip")
        self.assert_problem("T1 file: missing sheet(s) T1; found Sheet.", t1=save({"Sheet": [["x"]]}))
        self.files.set_t1("Istarska", "total", "employed", 7, "x")
        self.files.set_series("9.4.13.", "Istarska", 2026, 1, "total", "y")
        problems = self.problems()
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(problems[0].startswith("T1!E42: "), problems)
        self.assertTrue(problems[1].startswith("9.4.13.!I25: "), problems)

    def test_unpacked_size_is_limited(self) -> None:
        parser = DzsReleaseParser(CroatianCountyCatalog(), max_unpacked_bytes=1000)
        with self.assertRaises(DzsValidationError) as error:
            parser.parse(self.files.t1_bytes(), self.files.workbook_bytes())
        self.assertEqual(len(error.exception.problems), 2)
        self.assertIn("unpacks to", error.exception.problems[0])
        with self.assertRaises(ValueError):
            DzsReleaseParser(CroatianCountyCatalog(), max_unpacked_bytes=0)


if __name__ == "__main__":
    unittest.main()
