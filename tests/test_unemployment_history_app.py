import unittest
from datetime import date
from decimal import Decimal

from FOIHireloom.api.apps.labels import UNAVAILABLE_REASONS
from FOIHireloom.api.apps.unemployment_history import unemployment_history
from FOIHireloom.api.apps.views import UNEMPLOYMENT_HISTORY
from FOIHireloom.dto.county_indicators import (
    CountyUnemploymentHistoryDTO,
    SourceDTO,
    UnemploymentHistoryDTO,
    UnemploymentPointDTO,
)

SOURCES = (SourceDTO(name="DZS release table T1", url="https://podaci.dzs.hr/t1.xlsx", description="English"),)


def point(year: int, month: int, rate: str | None, provisional: bool | None = False) -> UnemploymentPointDTO:
    return UnemploymentPointDTO(period=date(year, month, 1), rate=None if rate is None else Decimal(rate),
                                is_provisional=None if rate is None else provisional,
                                unavailable_reason="dzs_value_missing" if rate is None else None)


def county(latest: UnemploymentPointDTO, before: UnemploymentPointDTO, name: str = "Varaždinska županija",
           ) -> CountyUnemploymentHistoryDTO:
    known = latest.rate is not None and before.rate is not None
    return CountyUnemploymentHistoryDTO(
        code=name.split()[0].casefold(), name=name, iso_code="HR-05", series=(before, latest), latest=latest,
        same_month_previous_year=before, change_pp=latest.rate - before.rate if known else None,
        change_unavailable_reason=None if known else "dzs_value_missing",
    )


def history(*counties: CountyUnemploymentHistoryDTO, sex: str = "total") -> UnemploymentHistoryDTO:
    return UnemploymentHistoryDTO(
        counties=counties, sex=sex, months=12, first_period=date(2025, 10, 1), last_period=date(2026, 9, 1),
        unavailable_reason=None, dzs=None, sources=SOURCES, notes=("English",),
    )


class UnemploymentHistoryAppTests(unittest.TestCase):
    def test_keeps_the_history_for_the_llm(self) -> None:
        data = history(county(point(2026, 9, "2.3", True), point(2025, 9, "2.9")))
        view = unemployment_history(data)
        self.assertEqual(view.model_dump(include=set(UnemploymentHistoryDTO.model_fields), exclude={"counties"}),
                         data.model_dump(exclude={"counties"}))
        self.assertEqual(view.counties[0].model_dump(include=set(CountyUnemploymentHistoryDTO.model_fields)),
                         data.counties[0].model_dump())
        self.assertEqual((view.counties[0].short_name, view.counties[0].change_unavailable_label), ("Varaždinska", None))
        self.assertEqual(view.model_dump(mode="json")["counties"][0]["change_pp"], -0.6)

    def test_title_description_and_notes(self) -> None:
        view = unemployment_history(history(county(point(2026, 9, "2.3", True), point(2025, 9, "2.9"))))
        self.assertEqual((view.title, view.description, view.unavailable_label),
                         ("Stopa registrirane nezaposlenosti", "Po mjesecima, listopad 2025. – rujan 2026.", None))
        self.assertEqual([link.label for link in view.source_links], ["DZS, priopćenje o zaposlenosti (tablica T1)"])
        self.assertIn("nije sezonska prilagodba", " ".join(view.view_notes))
        self.assertIn("privremeni", view.view_notes[-1])
        final = unemployment_history(history(county(point(2025, 9, "2.3"), point(2024, 9, "2.9"))))
        self.assertEqual(len(final.view_notes), 2)
        self.assertEqual(unemployment_history(history(sex="women")).title, "Stopa registrirane nezaposlenosti (žene)")
        self.assertEqual(unemployment_history(history(sex="men")).title, "Stopa registrirane nezaposlenosti (muškarci)")

    def test_unavailable_change_names_the_missing_month(self) -> None:
        view = unemployment_history(history(
            county(point(2026, 2, "2.3", True), point(2025, 2, None)),
            county(point(2026, 9, None), point(2025, 9, "2.9"), "Istarska županija"),
            county(point(2026, 9, None), point(2025, 9, None), "Ličko-senjska županija"),
        ))
        self.assertEqual([item.change_unavailable_label for item in view.counties], [
            "DZS nema stopu za veljaču 2025.", "DZS nema stopu za rujan 2026.",
            "DZS nema stopu za rujan 2025. i rujan 2026.",
        ])

    def test_without_a_series_says_why(self) -> None:
        for reason, label in (("no_dzs_data", "DZS podaci nisu uvezeni."),
                              ("no_common_period", "Nijedan mjesec nema DZS podatak za sve odabrane županije.")):
            empty = CountyUnemploymentHistoryDTO(code="varazdinska", name="Varaždinska županija", iso_code="HR-05",
                                                 series=(), latest=None, same_month_previous_year=None, change_pp=None,
                                                 change_unavailable_reason=reason)
            data = history(empty).model_copy(update={"first_period": None, "last_period": None,
                                                     "unavailable_reason": reason})
            view = unemployment_history(data)
            with self.subTest(reason=reason):
                self.assertEqual((view.description, view.unavailable_label), ("Podaci nisu dostupni", label))
                self.assertEqual(view.counties[0].change_unavailable_label, UNAVAILABLE_REASONS[reason])

    def test_built_page_draws_the_lines_and_marks_provisional_months_and_gaps(self) -> None:
        html = UNEMPLOYMENT_HISTORY.page()
        for expected in ("privremeni podaci", "prekid: nema podatka", "nema podatka", "promjena nije dostupna",
                         "prema istom mjesecu prošle godine", "stroke-dasharray", "DZS podaci uvezeni",
                         "unemployment-growth-chart", "Odabrani mjesec"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)
