"""Small DZS T1 and county workbooks built in memory, laid out like the real files.

The numbers are made up but consistent: T1 active = employed + unemployed,
county unemployed add up to Croatia's, and the workbook repeats T1's active
population and rates. Tests edit the grids before saving to break one rule.
"""

import io
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from openpyxl import Workbook

# DZS row labels in ISO 3166-2:HR order, HR-01 … HR-21.
COUNTY_LABELS = (
    "Zagrebačka", "Krapinsko-zagorska", "Sisačko-moslavačka", "Karlovačka", "Varaždinska",
    "Koprivničko-križevačka", "Bjelovarsko-bilogorska", "Primorsko-goranska", "Ličko-senjska",
    "Virovitičko-podravska", "Požeško-slavonska", "Brodsko-posavska", "Zadarska", "Osječko-baranjska",
    "Šibensko-kninska", "Vukovarsko-srijemska", "Splitsko-dalmatinska", "Istarska", "Dubrovačko-neretvanska",
    "Međimurska", "Grad Zagreb",
)
CROATIA = "Republika Hrvatska"
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
T1_YEAR, T1_MONTHS = 2026, (7, 8, 9)
# Workbook months: November 2025 to September 2026, after one annual average.
SERIES_MONTHS = tuple((2025, month) for month in (11, 12)) + tuple((2026, month) for month in range(1, 10))
NON_RESIDENTS = 500
T1_GROUPS = ("active_population", "employed", "unemployed", "unemployment_rate")
SEX_HEADERS = {"total": "ukupno Total", "men": "muškarci Men", "women": "žene Women"}


def rate(unemployed: int, active: int) -> int | float:
    """One-decimal rate as DZS stores it: round values come as int."""
    value = (Decimal(unemployed) * 100 / Decimal(active)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return int(value) if value == value.to_integral_value() else float(value)


def county_numbers(index: int, year: int, month: int) -> dict[str, dict[str, int]]:
    active = 20000 + 1000 * index + 7 * month + (year - 2025) * 50
    unemployed = 400 + 13 * index + month % 5
    women = {"active": active * 47 // 100, "unemployed": unemployed * 55 // 100}
    total = {"active": active, "unemployed": unemployed}
    men = {key: total[key] - women[key] for key in total}
    return {"total": total, "women": women, "men": men}


def area_numbers(year: int, month: int) -> dict[str, dict[str, dict[str, int]]]:
    """Persons by area label and sex, with Croatia including non-residents in the active population."""
    areas = {label: county_numbers(index, year, month) for index, label in enumerate(COUNTY_LABELS)}
    croatia = {}
    for sex in ("total", "women", "men"):
        croatia[sex] = {key: sum(areas[label][sex][key] for label in COUNTY_LABELS) for key in ("active", "unemployed")}
    croatia["total"]["active"] += NON_RESIDENTS
    croatia["women"]["active"] += NON_RESIDENTS // 2
    croatia["men"]["active"] += NON_RESIDENTS - NON_RESIDENTS // 2
    return {CROATIA: croatia} | areas


def cell_values(numbers: dict[str, int]) -> dict[str, int | float]:
    return {
        "active_population": numbers["active"], "employed": numbers["active"] - numbers["unemployed"],
        "unemployed": numbers["unemployed"], "unemployment_rate": rate(numbers["unemployed"], numbers["active"]),
    }


class DzsFiles:
    """Editable grids for the T1 file and the workbook's sheets 9.4.13 and 9.4.14 (0-based rows and columns)."""

    def __init__(self) -> None:
        self.t1 = self._t1()
        self.sheets = {"9.4.13.": self._series("active_population"), "9.4.14.": self._series("unemployment_rate")}

    # T1: title, two header rows, then each area's total row followed by its "Žene" row.
    @staticmethod
    def _t1() -> list[list[Any]]:
        groups = ["Aktivno stanovništvo1)", "Ukupno zaposleni1)2)", "Nezaposleni", "Stopa registrirane nezaposlenosti, %1)"]
        header = ["Županija"]
        for group in groups:
            header += [group, None, None]
        rows = [[None], [f"1. AKTIVNO STANOVNIŠTVO PREMA ADMINISTRATIVNIM IZVORIMA PO ŽUPANIJAMA I PREMA SPOLU U {T1_YEAR}."],
                [], header, [None] + [f"{ROMAN[month - 1]}." for month in T1_MONTHS] * 4]
        by_month = {month: area_numbers(T1_YEAR, month) for month in T1_MONTHS}
        for label in (CROATIA, *COUNTY_LABELS):
            for sex, row_label in (("total", label), ("women", "Žene")):
                cells = [row_label]
                for indicator in T1_GROUPS:
                    cells += [cell_values(by_month[month][label][sex])[indicator] for month in T1_MONTHS]
                rows.append(cells)
        rows += [[], [], ["1) Privremeni podatak."],
                 ["2) Nisu iskazani podaci o nerezidentima. Vidi Metodološka objašnjenja."]]
        return rows

    @staticmethod
    def _series(indicator: str) -> list[list[Any]]:
        if indicator == "active_population":
            sexes = ("total", "women")
            top = [["9.4.13."], ["AKTIVNO STANOVNIŠTVO PO ŽUPANIJAMA1)"], ["ACTIVE POPULATION BY COUNTIES1)"], [], []]
            notes = [["1) Podaci od 2026. privremeni su."], [], ["1) Since 2026, the data have been provisional."]]
        else:
            sexes = ("total", "men", "women")
            top = [["9.4.14."], ["STOPA REGISTRIRANE NEZAPOSLENOSTI PO ŽUPANIJAMA I PREMA  SPOLU1)2)"],
                   ["REGISTERED UNEMPLOYMENT RATE, BY COUNTIES AND BY SEX1)2)"], [], [None, "%"]]
            notes = [["1) Stopa registrirane nezaposlenosti izračunana je kao odnos nezaposlenih prema ukupnome "
                      "aktivnom stanovništvu."], ["2) Podaci od 2026. privremeni su."], [],
                     ["2) Since 2026, the data have been provisional."]]
        header = ["Županija", "County of"] + [f"Ø 2025.  {SEX_HEADERS[sex]}" for sex in sexes]
        # Spacing and line breaks as in the real headers.
        header += [f"{ROMAN[month - 1]}. {year}. {'' if sex == 'total' else chr(10)}{SEX_HEADERS[sex]}\n"
                   for year, month in SERIES_MONTHS for sex in sexes]
        rows = top + [header]
        by_month = {(year, month): area_numbers(year, month) for year, month in SERIES_MONTHS}
        for label in (CROATIA, *COUNTY_LABELS):
            cells = [label, "English name"] + [12345] * len(sexes)
            cells += [cell_values(by_month[period][label][sex])[indicator] for period in SERIES_MONTHS for sex in sexes]
            rows.append(cells)
        return rows + [[], []] + notes

    def t1_cell(self, label: str, sex: str, indicator: str, month: int) -> tuple[int, int]:
        """Return the (row, column) of a T1 value; label is the area's row label."""
        row = next(index for index, cells in enumerate(self.t1) if cells and cells[0] == label)
        return row + (sex == "women"), 1 + T1_GROUPS.index(indicator) * len(T1_MONTHS) + T1_MONTHS.index(month)

    def series_cell(self, sheet: str, label: str, year: int, month: int, sex: str) -> tuple[int, int]:
        rows = self.sheets[sheet]
        sexes = ("total", "women") if sheet == "9.4.13." else ("total", "men", "women")
        row = next(index for index, cells in enumerate(rows) if cells and cells[0] == label)
        return row, 2 + len(sexes) * (1 + SERIES_MONTHS.index((year, month))) + sexes.index(sex)

    def set_t1(self, label: str, sex: str, indicator: str, month: int, value: Any) -> None:
        row, column = self.t1_cell(label, sex, indicator, month)
        self.t1[row][column] = value

    def get_t1(self, label: str, sex: str, indicator: str, month: int) -> Any:
        row, column = self.t1_cell(label, sex, indicator, month)
        return self.t1[row][column]

    def set_series(self, sheet: str, label: str, year: int, month: int, sex: str, value: Any) -> None:
        row, column = self.series_cell(sheet, label, year, month, sex)
        self.sheets[sheet][row][column] = value

    def get_series(self, sheet: str, label: str, year: int, month: int, sex: str) -> Any:
        row, column = self.series_cell(sheet, label, year, month, sex)
        return self.sheets[sheet][row][column]

    def t1_bytes(self) -> bytes:
        return save({"T1": self.t1, "T2": [["2. ZAPOSLENI U PRAVNIM OSOBAMA"]]})

    def workbook_bytes(self) -> bytes:
        return save({"Sadrzaj-Contents": [["Sadržaj"]], **self.sheets, "Ispravci-Corrections": [["Sisačko-moslavčka"]]})


def save(sheets: dict[str, Iterable[Iterable[Any]]]) -> bytes:
    """Return the sheets as XLSX bytes. The archive embeds save times, so compare
    hashes with the bytes actually used, never with a second call."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(name)
        for row in rows:
            worksheet.append(list(row))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
