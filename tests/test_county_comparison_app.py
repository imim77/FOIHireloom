import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import get_args

from FOIHireloom.api.apps.county_comparison import DISCLAIMER, county_comparison
from FOIHireloom.api.apps.labels import UNAVAILABLE_REASONS, month_label, source_links
from FOIHireloom.api.apps.views import COUNTY_COMPARISON
from FOIHireloom.dto.county_indicators import (
    ComparedCountyDTO,
    CountyComparisonDTO,
    CountyIndicatorDTO,
    CountyJobCountsDTO,
    DzsCountyValueDTO,
    ShareDTO,
    SourceDTO,
    UnavailableReason,
)
from FOIHireloom.dto.dzs import DzsIndicator
from FOIHireloom.dto.job_market import JobCountFiltersDTO
from FOIHireloom.dto.job_search import CoverageDTO, RegionFreshnessDTO

TODAY = date(2026, 11, 2)
SEP = date(2026, 9, 1)
CHECKED = datetime(2026, 10, 31, 19, 3, tzinfo=UTC)
FRESH = CoverageDTO(data_status="fresh", data_as_of=CHECKED, stale_after_hours=6, affected_regions=(), warning=None)
COUNTS = CountyJobCountsDTO(
    jobs=10, workers_needed=13, workers_needed_coverage=ShareDTO(part=9, whole=10, percent=Decimal("90.0")),
    permanent_share=ShareDTO(part=4, whole=9, percent=Decimal("44.4")),
    contract_coverage=ShareDTO(part=9, whole=10, percent=Decimal("90.0")), closing_soon=4,
)
SOURCES = (
    SourceDTO(name="HZZ", url="https://burzarada.hzz.hr", description="English"),
    SourceDTO(name="DZS release table T1", url="https://podaci.dzs.hr/t1.xlsx", description="English"),
    SourceDTO(name="DZS county workbook", url=None, description="English, read from a local file"),
)


def value(indicator: DzsIndicator, number: str | None, provisional: bool | None = False,
          reason: UnavailableReason | None = None, period: date | None = SEP) -> DzsCountyValueDTO:
    return DzsCountyValueDTO(indicator=indicator, value=None if number is None else Decimal(number), period=period,
                             is_provisional=provisional, source=None if number is None else "t1",
                             unavailable_reason=reason)


def ratio(number: str | None, reason: UnavailableReason | None = None) -> CountyIndicatorDTO:
    return CountyIndicatorDTO(value=None if number is None else Decimal(number), numerator=1721,
                              denominator=None if number is None else 695, dzs_period=SEP, is_provisional=False,
                              unavailable_reason=reason)


def county(code: str = "varazdinska", name: str = "Varaždinska županija", **changes: object) -> ComparedCountyDTO:
    fields = dict(
        code=code, name=name, iso_code="HR-05", hzz_data_status="fresh", hzz_last_success_at=CHECKED,
        filtered_jobs=COUNTS, all_active_jobs=COUNTS, unemployed=value("unemployed", "1721"),
        active_population=value("active_population", "73662"), unemployment_rate=value("unemployment_rate", "2.3"),
        unemployed_per_worker=ratio("2.5"), jobs_per_1000_active=ratio("5.5"),
    )
    return ComparedCountyDTO(**{**fields, **changes})


def comparison(*counties: ComparedCountyDTO, filters: JobCountFiltersDTO = JobCountFiltersDTO(),
               coverage: CoverageDTO = FRESH) -> CountyComparisonDTO:
    return CountyComparisonDTO(
        counties=counties or (county(), county("medimurska", "Međimurska županija")), today=TODAY, filters=filters,
        requested_period=None, dzs_periods=(), hzz_coverage=coverage, dzs=None, sources=SOURCES,
        notes=("English note",),
    )


class CountyComparisonAppTests(unittest.TestCase):
    def test_keeps_the_comparison_for_the_llm(self) -> None:
        compared = comparison(county(unemployed_per_worker=ratio(None, "no_known_workers")),
                              county("grad-zagreb", "Grad Zagreb"))
        view = county_comparison(compared)
        self.assertEqual(CountyComparisonDTO.model_validate(view.model_dump()), compared)
        self.assertEqual(view.counties[0].unemployed_per_worker.unavailable_label,
                         UNAVAILABLE_REASONS["no_known_workers"])
        self.assertEqual([item.short_name for item in view.counties], ["Varaždinska", "Grad Zagreb"])

    def test_title_description_notes_and_disclaimer(self) -> None:
        view = county_comparison(comparison())
        self.assertEqual((view.title, view.description, view.coverage_note),
                         ("Usporedba županija", "Aktivni oglasi na dan 02. 11. 2026.", None))
        self.assertEqual(view.disclaimer, DISCLAIMER)
        self.assertIn("ne cijelo tržište rada ni osobnu vjerojatnost zaposlenja", view.disclaimer)
        self.assertEqual(len(view.view_notes), 2)
        filtered = county_comparison(comparison(filters=JobCountFiltersDTO(query=" kuhar ", include_expired=True)))
        self.assertEqual(filtered.description, "Upit „kuhar” · svi oglasi na dan 02. 11. 2026.")
        provisional = county_comparison(comparison(county(active_population=value("active_population", "1", True)),
                                                   county("medimurska", "Međimurska županija")))
        self.assertEqual(provisional.view_notes[-1], "DZS podaci za mjesece 2026. su privremeni i mogu se revidirati.")

    def test_coverage_warning_is_in_croatian(self) -> None:
        stale = FRESH.model_copy(update={"data_status": "stale", "warning": "English", "affected_regions": (
            RegionFreshnessDTO(code="varazdinska", name="Varaždinska županija", data_status="stale",
                               last_success_at=CHECKED),)})
        self.assertEqual(county_comparison(comparison(coverage=stale)).coverage_note,
                         "Varaždinska županija: podaci su stariji od 6 sati, pa rezultat možda nije potpun.")

    def test_unavailable_values_say_why_in_croatian(self) -> None:
        missing = value("unemployed", None, None, "dzs_value_missing", date(2025, 2, 1))
        view = county_comparison(comparison(
            county(unemployed=missing, unemployed_per_worker=ratio(None, "dzs_value_missing"),
                   jobs_per_1000_active=ratio(None, "zero_denominator")),
            county("istarska", "Istarska županija", unemployed=value("unemployed", None, None, "no_dzs_data", None),
                   unemployed_per_worker=ratio(None, "no_dzs_data"),
                   jobs_per_1000_active=ratio(None, "no_hzz_data")),
            county("medimurska", "Međimurska županija", unemployed_per_worker=ratio(None, "zero_denominator")),
        ))
        labels = [(item.unemployed.unavailable_label, item.unemployed_per_worker.unavailable_label,
                   item.jobs_per_1000_active.unavailable_label) for item in view.counties]
        self.assertEqual(labels, [
            ("DZS nema podatak za veljaču 2025.", "DZS nema podatak o nezaposlenima za veljaču 2025.",
             "aktivno stanovništvo je 0"),
            ("DZS podaci nisu uvezeni", "DZS podaci nisu uvezeni", "HZZ oglasi za županiju nisu učitani"),
            (None, "županija nema aktivnih oglasa", None),
        ])
        self.assertIsNone(view.counties[2].unemployment_rate.unavailable_label)

    def test_every_reason_has_a_croatian_label(self) -> None:
        self.assertEqual(set(UNAVAILABLE_REASONS), set(get_args(UnavailableReason.__value__)))
        for reason in UNAVAILABLE_REASONS:
            view = county_comparison(comparison(county(
                unemployment_rate=value("unemployment_rate", None, None, reason, None),
                unemployed_per_worker=ratio(None, reason))))
            with self.subTest(reason=reason):
                self.assertTrue(view.counties[0].unemployment_rate.unavailable_label)
                self.assertTrue(view.counties[0].unemployed_per_worker.unavailable_label)

    def test_sources_and_months_in_croatian(self) -> None:
        self.assertEqual([(link.label, link.url) for link in source_links(SOURCES)], [
            ("HZZ, burza rada (oglasi)", "https://burzarada.hzz.hr"),
            ("DZS, priopćenje o zaposlenosti (tablica T1)", "https://podaci.dzs.hr/t1.xlsx"),
            ("DZS, pregled po županijama (listovi 9.4.13 i 9.4.14) (lokalna datoteka)", None),
        ])
        self.assertEqual([month_label(date(2026, month, 1)) for month in (1, 2, 9, 12)],
                         ["siječanj 2026.", "veljača 2026.", "rujan 2026.", "prosinac 2026."])
        self.assertEqual(month_label(date(2026, 2, 1), accusative=True), "veljaču 2026.")
        self.assertEqual(month_label(date(2026, 11, 1), accusative=True), "studeni 2026.")

    def test_built_page_shows_the_table_the_moments_and_the_unavailable_values(self) -> None:
        html = COUNTY_COMPARISON.page()
        for expected in ("Usporedba županija", "Pokazatelji za županiju u cjelini", "svi aktivni oglasi, bez filtara",
                         "pokazatelj nije dostupan", "HZZ oglasi provjereni", "DZS referentni mjesec",
                         "Nezaposlenih na jednog traženog radnika", "Oglasa na 1.000 aktivnih stanovnika",
                         "privremeno", "show_county_comparison", "position:sticky", "Europe/Zagreb"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)
