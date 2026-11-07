"""Croatian labels for a county's Chronos forecast; source values and model intervals stay unchanged."""

from FOIHireloom.dto.dzs import DzsSex
from FOIHireloom.dto.forecast import (
    CountyForecastDTO,
    CountyForecastSeriesDTO,
    CountyForecastViewDTO,
    ForecastFrequency,
    ForecastTarget,
)

from .labels import PROVISIONAL_NOTE, month_label, source_links

TITLES: dict[ForecastTarget, str] = {
    "unemployment_rate": "Prognoza stope nezaposlenosti",
    "unemployed": "Prognoza broja nezaposlenih",
    "employed": "Prognoza broja zaposlenih",
    "job_ads": "Prognoza broja oglasa",
}
# job_ads has no sex, and a total needs no word.
WHOSE: dict[DzsSex | None, str] = {None: "", "total": "", "women": " · žene", "men": " · muškarci"}
FREQUENCIES: dict[ForecastFrequency, str] = {"month": "po mjesecima", "week": "po tjednima"}
UNAVAILABLE = {
    "no_dzs_data": "DZS podaci nisu uvezeni. Za prognozu prvo uvezite DZS podatke.",
    "no_common_period": "Za odabranu županiju nema odgovarajućih DZS podataka za prognozu.",
    "no_hzz_data": "HZZ oglasi nisu učitani. Za prognozu prvo uvezite HZZ oglase.",
}
NOT_ENOUGH_WEEKS = ("Za prognozu je potrebno najmanje 8 punih tjedana praćenja HZZ oglasa. Nastavite prikupljati "
                    "podatke.")
NOT_ENOUGH_MONTHS = "Za prognozu su potrebna najmanje 24 mjeseca s poznatim DZS vrijednostima."
NOTE_MODEL = ("Amazon Chronos procjenjuje nastavak povijesnog niza. Prognoza ne uključuje nove gospodarske "
              "šokove ili promjene politika i nije jamstvo budućih vrijednosti.")
NOTE_INTERVAL = "Medijan je središnja prognoza; donja i gornja granica prikazuju 80% interval (10. i 90. percentil)."
NOTE_JOB_ADS = "Broje se novi oglasi po tjednu objave, uključujući istekle. Jedan oglas može tražiti više radnika."
NOTE_RATE_CHANGE = "Promjena stope izražena je u postotnim bodovima (p. b.)."
NOTE_ESTIMATED = ("Povijesni brojevi označeni kao procijenjeni izračunati su iz DZS stope nezaposlenosti i aktivnog "
                  "stanovništva. Izravno objavljeni brojevi imaju prednost.")


def labour_market_forecast(data: CountyForecastDTO) -> CountyForecastViewDTO:
    county = data.counties[0]
    return CountyForecastViewDTO(
        **data.model_dump(), title=TITLES[data.target],
        description=f"{county.name}{WHOSE[data.sex]} · {FREQUENCIES[data.frequency]}",
        unavailable_label=unavailable_label(data, county), source_links=source_links(data.sources),
        view_notes=(NOTE_MODEL, NOTE_INTERVAL, *_series_notes(data, county)),
    )


def unavailable_label(data: CountyForecastDTO, county: CountyForecastSeriesDTO) -> str | None:
    """Why the county has no forecast and what would give it one; None when it has one."""
    reason = county.unavailable_reason or data.unavailable_reason
    if reason == "not_enough_history":
        return NOT_ENOUGH_WEEKS if data.target == "job_ads" else NOT_ENOUGH_MONTHS
    return UNAVAILABLE.get(reason)


def _series_notes(data: CountyForecastDTO, county: CountyForecastSeriesDTO) -> list[str]:
    """What the weekly HZZ ad counts or the monthly DZS values mean for this forecast."""
    if data.target == "job_ads":
        return [NOTE_JOB_ADS]
    notes = []
    if data.last_observed_period is not None:
        notes.append(f"Zadnji DZS mjesec: {month_label(data.last_observed_period)} Prognoza počinje sljedećim "
                     "mjesecom, koji zbog kašnjenja objave već može biti u prošlosti.")
    if data.target == "unemployment_rate":
        notes.append(NOTE_RATE_CHANGE)
    if any(point.is_estimated for point in county.history):
        notes.append(NOTE_ESTIMATED)
    if any(point.is_provisional for point in county.history):
        notes.append(PROVISIONAL_NOTE)
    return notes
