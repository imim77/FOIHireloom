import io
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from FOIHireloom.dto.dzs import DzsReleaseDTO, DzsSeriesDTO, DzsValueDTO
from FOIHireloom.exceptions import DzsValidationError

from .croatian_counties import CroatianCountyCatalog

ROMAN_MONTHS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
}
# Croatian sex label -> (stored sex, the English label that must follow it).
SEXES = {"ukupno": ("total", "Total"), "muškarci": ("men", "Men"), "žene": ("women", "Women")}
MARKERS = {"-": "no_occurrence", "…": "not_available", "...": "not_available", "": "empty"}
CROATIA = "Republika Hrvatska"
HEADER = "Županija"
WOMEN_ROW = "Žene"
FOOTNOTE = re.compile(r"(\d)\)\s*(.+)")
NOTE_MARK = re.compile(r"(\d)\)")

T1_SHEET = "T1"
T1_TITLE = re.compile(
    r"1\. AKTIVNO STANOVNIŠTVO (?:PREMA )?ADMINISTRATIVNIM IZVORIMA PO ŽUPANIJAMA I PREMA SPOLU U (?P<year>\d{4})\."
)
T1_GROUPS = (
    ("Aktivno stanovništvo", "active_population"),
    ("Ukupno zaposleni", "employed"),
    ("Nezaposleni", "unemployed"),
    ("Stopa registrirane nezaposlenosti, %", "unemployment_rate"),
)
T1_GROUP = re.compile(r"(?P<name>.*?)(?P<notes>(?:\d\))*)")
T1_MONTH = re.compile(r"(?P<month>[IVX]+)\.")
T1_PROVISIONAL = "Privremeni podatak."

MONTH_HEADER = re.compile(
    r"(?P<month>[IVX]+)\. (?P<year>\d{4})\. (?P<sex>ukupno|muškarci|žene) (?P<sex_en>Total|Men|Women)"
)
AVERAGE_HEADER = re.compile(r"Ø ?\d{4}\. (?:ukupno|muškarci|žene) (?:Total|Men|Women)")
SERIES_PROVISIONAL = re.compile(r"Podaci od (?P<year>\d{4})\. privremeni su\.")


@dataclass(frozen=True)
class SeriesSheet:
    """A workbook sheet with one column per (month or annual average, sex) and one row per area."""

    name: str
    source: str
    title: str
    indicator: str
    sexes: frozenset[str]

    @property
    def title_pattern(self) -> re.Pattern[str]:
        return re.compile(re.escape(self.title) + r"(?P<notes>(?:\d\))*)")


SERIES_SHEETS = (
    SeriesSheet("9.4.13.", "workbook_9_4_13", "AKTIVNO STANOVNIŠTVO PO ŽUPANIJAMA", "active_population",
                frozenset({"total", "women"})),
    SeriesSheet("9.4.14.", "workbook_9_4_14", "STOPA REGISTRIRANE NEZAPOSLENOSTI PO ŽUPANIJAMA I PREMA SPOLU",
                "unemployment_rate", frozenset({"total", "men", "women"})),
)
SOURCE_ORDER = ("t1", *(sheet.source for sheet in SERIES_SHEETS))
# The sheets read from each file, by file role.
SHEETS = {"t1": (T1_SHEET,), "workbook": tuple(sheet.name for sheet in SERIES_SHEETS)}


def squash(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


class Sheet:
    """A worksheet's cell values by 0-based row and column; problems are reported with Excel cell references."""

    def __init__(self, name: str, rows: list[list[Any]], problems: list[str]) -> None:
        self.name = name
        self._rows = rows
        self._problems = problems

    @property
    def height(self) -> int:
        return len(self._rows)

    def width(self, row: int) -> int:
        return len(self._rows[row]) if row < len(self._rows) else 0

    def value(self, row: int, column: int) -> Any:
        cells = self._rows[row] if row < len(self._rows) else []
        return cells[column] if column < len(cells) else None

    def text(self, row: int, column: int) -> str:
        return squash(self.value(row, column))

    def find_row(self, label: str) -> int | None:
        return next((row for row in range(self.height) if self.text(row, 0) == label), None)

    def has_values(self, row: int, first_column: int) -> bool:
        return any(self.text(row, column) for column in range(first_column, self.width(row)))

    def problem(self, message: str, row: int | None = None, column: int = 0) -> None:
        where = self.name if row is None else f"{self.name}!{get_column_letter(column + 1)}{row + 1}"
        self._problems.append(f"{where}: {message}")


class DzsReleaseParser:
    """Read the DZS T1 release table and the county workbook into validated county values.

    The T1 file (one sheet, July–September of the title's year, total and
    women) gives exact unemployed counts. Workbook sheets 9.4.13 (active
    population) and 9.4.14 (unemployment rate, also for men) give the monthly
    series; annual averages are skipped. Every problem found in either file is
    collected, and any problem rejects the pair: nothing is returned.

    Counties are linked by CroatianCountyCatalog.match and must appear exactly
    once each, next to one "Republika Hrvatska" row. That row is used only for
    validation, as it includes non-residents. Cells are numbers or DZS markers
    ("-" no occurrence, "…" not available) or empty; none of these is a zero.

    Provisional status follows the source's footnotes: workbook months from
    the year of "Podaci od YYYY. privremeni su." on, and the T1 column groups
    marked with the "Privremeni podatak." footnote. For keys in both files, T1
    is kept after checking that the workbook agrees with it.
    """

    def __init__(self, catalog: CroatianCountyCatalog, max_unpacked_bytes: int = 128 * 1024 * 1024) -> None:
        if max_unpacked_bytes <= 0:
            raise ValueError("Unpacked size limit must be positive.")
        self._catalog = catalog
        self._max_unpacked_bytes = max_unpacked_bytes
        self._names: dict[str | None, str] = {county.iso_code: county.name for county in catalog.definitions}
        self._names[None] = CROATIA

    def parse(self, t1: bytes, workbook: bytes) -> DzsReleaseDTO:
        """Return the county values of both files, or raise DzsValidationError listing every problem."""
        problems: list[str] = []
        t1_values: list[DzsValueDTO] = []
        series: dict[str, list[DzsValueDTO]] = {}
        if sheets := self._load(t1, "T1 file", SHEETS["t1"], problems):
            t1_values = self._parse_t1(sheets[T1_SHEET])
        if sheets := self._load(workbook, "Workbook", SHEETS["workbook"], problems):
            series = {spec.source: self._parse_series(sheets[spec.name], spec) for spec in SERIES_SHEETS}
        if not problems:
            self._check_t1(t1_values, problems)
            for spec in SERIES_SHEETS:
                self._check_agreement(t1_values, series[spec.source], spec, problems)
        if problems:
            raise DzsValidationError(problems)
        return self._release(t1_values, series)

    def _load(
        self, content: bytes, label: str, sheet_names: tuple[str, ...], problems: list[str]
    ) -> dict[str, Sheet] | None:
        """Read the named sheets, or record why they cannot be read and return None."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                unpacked = sum(info.file_size for info in archive.infolist())
        except zipfile.BadZipFile:
            problems.append(f"{label}: not an XLSX workbook.")
            return None
        if unpacked > self._max_unpacked_bytes:
            problems.append(f"{label}: unpacks to {unpacked} bytes, more than {self._max_unpacked_bytes}.")
            return None
        # openpyxl parses the XML with defusedxml, which the project depends on.
        # It raises many unrelated types for a malformed package, so any error
        # while reading is a problem with the file.
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
        except Exception as error:
            problems.append(f"{label}: cannot be read as an XLSX workbook ({type(error).__name__}).")
            return None
        try:
            names = {squash(name): name for name in workbook.sheetnames}
            missing = [name for name in sheet_names if name not in names]
            if missing:
                problems.append(f"{label}: missing sheet(s) {', '.join(missing)}; found {', '.join(names)}.")
                return None
            sheets = {}
            for name in sheet_names:
                worksheet = workbook[names[name]]
                # The stored dimension can be wrong; read every cell that is present.
                worksheet.reset_dimensions()
                sheets[name] = Sheet(name, [list(row) for row in worksheet.iter_rows(values_only=True)], problems)
            return sheets
        except Exception as error:
            problems.append(f"{label}: cannot be read as an XLSX workbook ({type(error).__name__}).")
            return None
        finally:
            workbook.close()

    def _parse_t1(self, sheet: Sheet) -> list[DzsValueDTO]:
        header = sheet.find_row(HEADER)
        if header is None:
            sheet.problem(f"no header row starting with {HEADER!r}.")
            return []
        titles = [match for row in range(header) if (match := T1_TITLE.fullmatch(sheet.text(row, 0)))]
        if not titles:
            sheet.problem("title '1. AKTIVNO STANOVNIŠTVO … PO ŽUPANIJAMA I PREMA SPOLU U YYYY.' not found.")
            return []
        year = int(titles[0]["year"])
        groups = self._t1_groups(sheet, header)
        rows, notes = self._rows(sheet, header + 2)
        provisional = {number for number, text in notes if text == T1_PROVISIONAL}
        if not provisional:
            sheet.problem(f"footnote {T1_PROVISIONAL!r} not found.")
        if groups is None:
            return []
        values = []
        for county_iso, sex, row in self._t1_areas(sheet, rows):
            for indicator, marks, columns in groups:
                for column, month in columns:
                    if (cell := self._cell(sheet, row, column, indicator)) is not None:
                        values.append(DzsValueDTO(
                            county_iso=county_iso, indicator=indicator, period=date(year, month, 1), sex=sex,
                            value=cell[0], missing_reason=cell[1], is_provisional=bool(marks & provisional),
                            source="t1",
                        ))
        return values

    def _t1_groups(self, sheet: Sheet, header: int) -> list[tuple[str, set[str], list[tuple[int, int]]]] | None:
        """Return (indicator, footnote marks, [(column, month)]) per column group of the two header rows."""
        starts = [column for column in range(1, sheet.width(header)) if sheet.text(header, column)]
        labels = [T1_GROUP.fullmatch(sheet.text(header, column)) for column in starts]
        found = [label["name"] for label in labels]
        if found != [name for name, _ in T1_GROUPS]:
            sheet.problem(f"expected column groups {[name for name, _ in T1_GROUPS]}, found {found}.", header)
            return None
        months_row, groups = header + 1, []
        for index, (start, label) in enumerate(zip(starts, labels)):
            end = starts[index + 1] if index + 1 < len(starts) else sheet.width(months_row)
            span = list(range(start, end))
            if index + 1 == len(starts):
                while span and not sheet.text(months_row, span[-1]):
                    span.pop()
            columns = []
            for column in span:
                match = T1_MONTH.fullmatch(sheet.text(months_row, column))
                if match is None or match["month"] not in ROMAN_MONTHS:
                    sheet.problem(f"expected a Roman month such as 'IX.', found {sheet.text(months_row, column)!r}.",
                                  months_row, column)
                    return None
                columns.append((column, ROMAN_MONTHS[match["month"]]))
            groups.append((T1_GROUPS[index][1], set(NOTE_MARK.findall(label["notes"])), columns))
        months = [[month for _, month in columns] for _, _, columns in groups]
        first = months[0]
        if not first or any(group != first for group in months) or first != list(range(first[0], first[0] + len(first))):
            sheet.problem(f"column groups must cover the same consecutive months, found {months}.", months_row)
            return None
        return groups

    def _t1_areas(self, sheet: Sheet, rows: list[tuple[int, str]]) -> list[tuple[str | None, str, int]]:
        """Pair each area row (total) with the "Žene" row below it (women)."""
        areas: list[tuple[str | None, str, int]] = []
        awaiting: str | None = None
        known, county_iso = False, None
        for row, label in rows:
            if label == WOMEN_ROW:
                if awaiting is None:
                    sheet.problem(f"{WOMEN_ROW!r} row without an area row above it.", row)
                elif known:
                    areas.append((county_iso, "women", row))
                awaiting = None
                continue
            if awaiting is not None:
                sheet.problem(f"no {WOMEN_ROW!r} row after {awaiting!r}.", row)
            known, county_iso = self._area(sheet, row, label)
            if known:
                areas.append((county_iso, "total", row))
            awaiting = label
        if awaiting is not None:
            sheet.problem(f"no {WOMEN_ROW!r} row after {awaiting!r}.")
        self._check_areas(sheet, [county_iso for county_iso, sex, _ in areas if sex == "total"])
        return areas

    def _parse_series(self, sheet: Sheet, spec: SeriesSheet) -> list[DzsValueDTO]:
        header = sheet.find_row(HEADER)
        if header is None:
            sheet.problem(f"no header row starting with {HEADER!r}.")
            return []
        if sheet.text(header, 1) != "County of":
            sheet.problem(f"expected 'County of', found {sheet.text(header, 1)!r}.", header, 1)
            return []
        titles = [match for row in range(header) if (match := spec.title_pattern.fullmatch(sheet.text(row, 0)))]
        if not titles:
            sheet.problem(f"title {spec.title!r} not found.")
            return []
        columns = self._series_columns(sheet, header, spec)
        rows, notes = self._rows(sheet, header + 1)
        provisional = [(number, int(match["year"])) for number, text in notes
                       if (match := SERIES_PROVISIONAL.fullmatch(text))]
        if not provisional:
            sheet.problem("footnote 'Podaci od YYYY. privremeni su.' not found.")
        elif provisional[0][0] not in NOTE_MARK.findall(titles[0]["notes"]):
            sheet.problem(f"the title does not refer to the provisional data footnote {provisional[0][0]}).")
        if columns is None or not provisional:
            return []
        first_provisional_year = provisional[0][1]
        values, areas = [], []
        for row, label in rows:
            known, county_iso = self._area(sheet, row, label)
            if not known:
                continue
            areas.append(county_iso)
            for column, period, sex in columns:
                if (cell := self._cell(sheet, row, column, spec.indicator)) is not None:
                    values.append(DzsValueDTO(
                        county_iso=county_iso, indicator=spec.indicator, period=period, sex=sex, value=cell[0],
                        missing_reason=cell[1], is_provisional=period.year >= first_provisional_year,
                        source=spec.source,
                    ))
        self._check_areas(sheet, areas)
        return values

    @staticmethod
    def _series_columns(sheet: Sheet, header: int, spec: SeriesSheet) -> list[tuple[int, date, str]] | None:
        """Return (column, month, sex) for each monthly column; annual averages are skipped."""
        last = sheet.width(header)
        while last > 2 and not sheet.text(header, last - 1):
            last -= 1
        columns, sexes, valid = [], defaultdict(set), True
        for column in range(2, last):
            label = sheet.text(header, column)
            if AVERAGE_HEADER.fullmatch(label):
                continue
            match = MONTH_HEADER.fullmatch(label)
            if match is None or match["month"] not in ROMAN_MONTHS or SEXES[match["sex"]][1] != match["sex_en"]:
                sheet.problem(f"unexpected column header {label!r}.", header, column)
                valid = False
                continue
            period, sex = date(int(match["year"]), ROMAN_MONTHS[match["month"]], 1), SEXES[match["sex"]][0]
            if sex in sexes[period]:
                sheet.problem(f"second column for {period:%Y-%m} {sex}.", header, column)
                valid = False
            sexes[period].add(sex)
            columns.append((column, period, sex))
        if not sexes:
            sheet.problem("no monthly columns.", header)
            return None
        for period, found in sorted(sexes.items()):
            if found != spec.sexes:
                sheet.problem(f"{period:%Y-%m} has columns for {sorted(found)}, expected {sorted(spec.sexes)}.", header)
                valid = False
        for earlier, later in pairwise(sorted(sexes)):
            if (later.year * 12 + later.month) - (earlier.year * 12 + earlier.month) != 1:
                sheet.problem(f"months between {earlier:%Y-%m} and {later:%Y-%m} are missing.", header)
                valid = False
        return columns if valid else None

    @staticmethod
    def _rows(sheet: Sheet, first: int) -> tuple[list[tuple[int, str]], list[tuple[str, str]]]:
        """Return the labelled rows from first up to the footnotes, and the footnotes as (number, text)."""
        rows, notes = [], []
        for row in range(first, sheet.height):
            label = sheet.text(row, 0)
            if match := FOOTNOTE.fullmatch(label):
                notes.append((match[1], match[2]))
            elif notes:
                continue
            elif label:
                rows.append((row, label))
            elif sheet.has_values(row, 1):
                sheet.problem("row has values but no label.", row)
        return rows, notes

    def _area(self, sheet: Sheet, row: int, label: str) -> tuple[bool, str | None]:
        """Return (known, ISO code), with ISO code None for the Croatia row."""
        if self._catalog.normalise(label) == self._catalog.normalise(CROATIA):
            return True, None
        county = self._catalog.match(label)
        if county is None:
            sheet.problem(f"unknown county label {label!r}.", row)
            return False, None
        return True, county.iso_code

    def _check_areas(self, sheet: Sheet, areas: list[str | None]) -> None:
        counts = Counter(areas)
        for county_iso, count in counts.items():
            if count > 1:
                sheet.problem(f"{count} rows for {self._names[county_iso]}.")
        if None not in counts:
            sheet.problem(f"no {CROATIA!r} row.")
        missing = [county.name for county in self._catalog.definitions if county.iso_code not in counts]
        if missing:
            sheet.problem(f"missing counties: {', '.join(sorted(missing))}.")

    @staticmethod
    def _cell(sheet: Sheet, row: int, column: int, indicator: str) -> tuple[Decimal | None, str | None] | None:
        """Return (value, missing reason), or record a problem and return None."""
        raw = sheet.value(row, column)
        if raw is None:
            return None, "empty"
        if isinstance(raw, str):
            if (marker := squash(raw)) in MARKERS:
                return None, MARKERS[marker]
            sheet.problem(f"{raw!r} is neither a number nor a DZS marker ('-', '…').", row, column)
            return None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            sheet.problem(f"{raw!r} is not a number.", row, column)
            return None
        number = Decimal(raw) if isinstance(raw, int) else Decimal(repr(raw))
        try:
            if indicator == "unemployment_rate":
                value = number.quantize(Decimal("0.1"))
                if value == number and 0 <= value <= 100:
                    return value, None
                sheet.problem(f"rate {raw!r} is not a percentage with one decimal.", row, column)
                return None
            if number >= 0 and number == number.to_integral_value():
                return number.quantize(Decimal(1)), None
        except InvalidOperation:
            pass
        sheet.problem(f"{raw!r} is not a whole number of persons.", row, column)
        return None

    def _check_t1(self, values: list[DzsValueDTO], problems: list[str]) -> None:
        """Active population is employed plus unemployed; county unemployed add up to Croatia's."""
        by_key = {value.key: value for value in values}
        for (county_iso, indicator, period, sex), active in by_key.items():
            if indicator != "active_population":
                continue
            employed = by_key[(county_iso, "employed", period, sex)].value
            unemployed = by_key[(county_iso, "unemployed", period, sex)].value
            if None not in (active.value, employed, unemployed) and active.value != employed + unemployed:
                problems.append(
                    f"T1: {self._names[county_iso]} {period:%Y-%m} {sex}: active population {active.value} is not "
                    f"employed {employed} + unemployed {unemployed}."
                )
        for period, sex in sorted({(value.period, value.sex) for value in values}):
            national = by_key[(None, "unemployed", period, sex)].value
            counties = [by_key[(county.iso_code, "unemployed", period, sex)].value for county in self._catalog.definitions]
            if national is not None and None not in counties and sum(counties) != national:
                problems.append(
                    f"T1: unemployed in the 21 counties add up to {sum(counties)}, not {national} for Croatia "
                    f"({period:%Y-%m} {sex})."
                )

    def _check_agreement(
        self, t1: list[DzsValueDTO], series: list[DzsValueDTO], spec: SeriesSheet, problems: list[str]
    ) -> None:
        """The workbook covers the T1 months and has the same values for the keys both files have."""
        by_key = {value.key: value for value in series}
        months = sorted({value.period for value in t1})
        uncovered = [month for month in months if (None, spec.indicator, month, "total") not in by_key]
        if uncovered:
            problems.append(f"{spec.name}: no columns for the T1 months {', '.join(f'{m:%Y-%m}' for m in uncovered)}.")
            return
        for value in t1:
            if value.indicator != spec.indicator:
                continue
            other = by_key[value.key]
            if (other.value, other.missing_reason) != (value.value, value.missing_reason):
                shown = [cell.missing_reason if cell.value is None else cell.value for cell in (value, other)]
                problems.append(
                    f"T1 and {spec.name} differ for {self._names[value.county_iso]} {value.period:%Y-%m} "
                    f"{value.sex}: {shown[0]} vs {shown[1]}."
                )

    @staticmethod
    def _release(t1: list[DzsValueDTO], series: dict[str, list[DzsValueDTO]]) -> DzsReleaseDTO:
        merged = {value.key: value for values in series.values() for value in values}
        # T1 is the source of record for the keys both files have.
        merged |= {value.key: value for value in t1}
        values = sorted((value for value in merged.values() if value.county_iso is not None),
                        key=lambda value: (value.county_iso, value.indicator, value.period, value.sex))
        by_source = defaultdict(list)
        for value in values:
            by_source[value.source].append(value)
        summaries = tuple(
            DzsSeriesDTO(
                source=source, values=len(group), provisional=sum(value.is_provisional for value in group),
                missing=sum(value.value is None for value in group),
                first_period=min(value.period for value in group), last_period=max(value.period for value in group),
            )
            for source in SOURCE_ORDER if (group := by_source[source])
        )
        return DzsReleaseDTO(values=tuple(values), series=summaries)
