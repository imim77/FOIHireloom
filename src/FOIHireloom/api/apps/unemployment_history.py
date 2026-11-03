"""Data for the unemployment history chart, which draws each county's monthly registered unemployment rate as a line.

The tool returns UnemploymentHistoryViewDTO as structured content; the host
loads the views.UNEMPLOYMENT_HISTORY page in a sandboxed iframe and passes
it that result over the MCP Apps bridge. Text-only hosts still get the same
data, the English fields included.
"""

from FOIHireloom.dto.county_indicators import (
    CountyUnemploymentHistoryDTO,
    CountyUnemploymentHistoryViewDTO,
    UnemploymentHistoryDTO,
    UnemploymentHistoryViewDTO,
)
from FOIHireloom.dto.dzs import DzsSex

from .labels import PROVISIONAL_NOTE, UNAVAILABLE_REASONS, month_label, sentence, source_links

TITLE = "Stopa registrirane nezaposlenosti"
WHOSE: dict[DzsSex, str] = {"total": "", "women": " (žene)", "men": " (muškarci)"}
NOTE_RATE = "Stopa je udio registriranih nezaposlenih u aktivnom stanovništvu, kako je objavljuje DZS."
NOTE_SEASONALITY = ("Usporedba s istim mjesecom prethodne godine smanjuje utjecaj sezone, koji je jak u priobalnim "
                    "županijama, ali nije sezonska prilagodba podataka.")


def unemployment_history(history: UnemploymentHistoryDTO) -> UnemploymentHistoryViewDTO:
    provisional = any(point.is_provisional for county in history.counties for point in county.series)
    unavailable = None if history.unavailable_reason is None else UNAVAILABLE_REASONS[history.unavailable_reason]
    return UnemploymentHistoryViewDTO(
        **history.model_dump(exclude={"counties"}),
        counties=tuple(_county(county) for county in history.counties),
        title=TITLE + WHOSE[history.sex],
        description=description(history),
        unavailable_label=None if unavailable is None else sentence(unavailable) + ".",
        source_links=source_links(history.sources),
        view_notes=(NOTE_RATE, NOTE_SEASONALITY, *([PROVISIONAL_NOTE] if provisional else [])),
    )


def description(history: UnemploymentHistoryDTO) -> str:
    """"Po mjesecima, listopad 2024. – rujan 2026.", or that there is no series."""
    if history.first_period is None or history.last_period is None:
        return "Podaci nisu dostupni"
    return f"Po mjesecima, {month_label(history.first_period)} – {month_label(history.last_period)}"


def change_reason(county: CountyUnemploymentHistoryDTO) -> str | None:
    """Why the change over a year is unavailable, naming the missing month; None when it is known."""
    reason = county.change_unavailable_reason
    if reason is None:
        return None
    if reason == "dzs_value_missing":
        missing = [point for point in (county.same_month_previous_year, county.latest)
                   if point is not None and point.rate is None]
        if missing:
            months = " i ".join(month_label(point.period, accusative=True) for point in missing)
            return f"DZS nema stopu za {months}"
    return UNAVAILABLE_REASONS[reason]


def _county(county: CountyUnemploymentHistoryDTO) -> CountyUnemploymentHistoryViewDTO:
    return CountyUnemploymentHistoryViewDTO(
        **county.model_dump(), short_name=county.name.removesuffix(" županija"),
        change_unavailable_label=change_reason(county),
    )
