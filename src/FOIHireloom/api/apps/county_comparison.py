"""Data for the county comparison view, which shows 2 to 6 counties side by side: HZZ ads, DZS values, indicators.

The tool returns CountyComparisonViewDTO as structured content; the host
loads the views.COUNTY_COMPARISON page in a sandboxed iframe and passes it
that result over the MCP Apps bridge. Text-only hosts still get the same
data, the English fields included.
"""

from FOIHireloom.dto.county_indicators import (
    ComparedCountyDTO,
    ComparedCountyViewDTO,
    CountyComparisonDTO,
    CountyComparisonViewDTO,
    CountyIndicatorDTO,
    CountyIndicatorViewDTO,
    DzsCountyValueDTO,
    DzsCountyValueViewDTO,
)
from FOIHireloom.dto.dzs import DzsIndicator

from .labels import (
    PROVISIONAL_NOTE,
    UNAVAILABLE_REASONS,
    coverage_note,
    day,
    month_label,
    query_label,
    sentence,
    short_county_name,
    source_links,
)

TITLE = "Usporedba županija"
DISCLAIMER = ("Pokazatelji opisuju HZZ oglase i registriranu nezaposlenost, a ne cijelo tržište rada ni osobnu "
              "vjerojatnost zaposlenja.")
NOTE_WORKERS = ("Traženi radnici zbrajaju se samo iz oglasa koji navode njihov broj, pa je broj nezaposlenih na "
                "jednog traženog radnika veći kad manje oglasa navodi broj.")
NOTE_MOMENTS = "HZZ oglasi su stanje u trenutku provjere, a DZS podaci za prošli referentni mjesec."
# What a DZS value is about, in "DZS nema podatak o … za rujan 2026.".
ABOUT: dict[DzsIndicator, str] = {
    "unemployed": "nezaposlenima",
    "active_population": "aktivnom stanovništvu",
    "unemployment_rate": "stopi nezaposlenosti",
    "employed": "zaposlenima",
}


def county_comparison(comparison: CountyComparisonDTO) -> CountyComparisonViewDTO:
    provisional = any(value.is_provisional for county in comparison.counties
                      for value in (county.unemployed, county.active_population, county.unemployment_rate))
    return CountyComparisonViewDTO(
        **comparison.model_dump(exclude={"counties"}),
        counties=tuple(_county(county) for county in comparison.counties),
        title=TITLE,
        description=description(comparison),
        coverage_note=coverage_note(comparison.hzz_coverage),
        source_links=source_links(comparison.sources),
        view_notes=(NOTE_WORKERS, NOTE_MOMENTS, *([PROVISIONAL_NOTE] if provisional else [])),
        disclaimer=DISCLAIMER,
    )


def description(comparison: CountyComparisonDTO) -> str:
    """The query, if any, and which ads on which day: "Upit „kuhar” · aktivni oglasi na dan 2. 11. 2026."."""
    parts = (query_label(comparison.filters.query), day(comparison.today, comparison.filters.include_expired))
    return sentence(" · ".join(part for part in parts if part))


def value_reason(value: DzsCountyValueDTO, about: bool = False) -> str | None:
    """Why a DZS value is unavailable, naming the month when it is known; None when the value is known.

    about names the value too, as an indicator needs: "DZS nema podatak o nezaposlenima za rujan 2025.".
    """
    if value.unavailable_reason is None:
        return None
    if value.unavailable_reason == "dzs_value_missing" and value.period is not None:
        subject = f" o {ABOUT[value.indicator]}" if about else ""
        return f"DZS nema podatak{subject} za {month_label(value.period, accusative=True)}"
    return UNAVAILABLE_REASONS[value.unavailable_reason]


def indicator_reason(indicator: CountyIndicatorDTO, dzs: DzsCountyValueDTO, per_worker: bool) -> str | None:
    """Why an indicator is unavailable; dzs is its DZS value. None when the indicator is known."""
    reason = indicator.unavailable_reason
    if reason is None:
        return None
    if reason == dzs.unavailable_reason:
        return value_reason(dzs, about=True)
    if reason == "zero_denominator":
        # A county without active ads seeks no workers through HZZ; a known 0 active population is a DZS value.
        return "županija nema aktivnih oglasa" if per_worker else "aktivno stanovništvo je 0"
    return UNAVAILABLE_REASONS[reason]


def _value(value: DzsCountyValueDTO) -> DzsCountyValueViewDTO:
    return DzsCountyValueViewDTO(**value.model_dump(), unavailable_label=value_reason(value))


def _indicator(indicator: CountyIndicatorDTO, dzs: DzsCountyValueDTO, per_worker: bool) -> CountyIndicatorViewDTO:
    return CountyIndicatorViewDTO(**indicator.model_dump(), unavailable_label=indicator_reason(indicator, dzs,
                                                                                                per_worker))


def _county(county: ComparedCountyDTO) -> ComparedCountyViewDTO:
    shown = {"unemployed", "active_population", "unemployment_rate", "unemployed_per_worker", "jobs_per_1000_active"}
    return ComparedCountyViewDTO(
        **county.model_dump(exclude=shown),
        short_name=short_county_name(county.name),
        unemployed=_value(county.unemployed),
        active_population=_value(county.active_population),
        unemployment_rate=_value(county.unemployment_rate),
        unemployed_per_worker=_indicator(county.unemployed_per_worker, county.unemployed, per_worker=True),
        jobs_per_1000_active=_indicator(county.jobs_per_1000_active, county.active_population, per_worker=False),
    )
