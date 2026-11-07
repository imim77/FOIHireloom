"""Croatian labels for a county's Chronos forecast; source values and model intervals stay unchanged."""

from FOIHireloom.dto.forecast import CountyForecastDTO, CountyForecastViewDTO, ForecastTarget

from .labels import PROVISIONAL_NOTE, month_label, source_links

TITLES: dict[ForecastTarget, str] = {
    "unemployment_rate": "Prognoza stope nezaposlenosti",
    "unemployed": "Prognoza broja nezaposlenih",
    "employed": "Prognoza broja zaposlenih",
    "job_ads": "Prognoza broja oglasa",
}
UNAVAILABLE = {
    "no_dzs_data": "DZS podaci nisu uvezeni. Za prognozu prvo uvezite DZS podatke.",
    "no_common_period": "Za odabranu županiju nema odgovarajućih DZS podataka za prognozu.",
    "no_hzz_data": "HZZ oglasi nisu učitani. Za prognozu prvo uvezite HZZ oglase.",
}
NOTE_MODEL = ("Amazon Chronos procjenjuje nastavak povijesnog niza. Prognoza ne uključuje nove gospodarske "
              "šokove ili promjene politika i nije jamstvo budućih vrijednosti.")
NOTE_INTERVAL = "Medijan je središnja prognoza; donja i gornja granica prikazuju 80% interval (10. i 90. percentil)."
NOTE_ESTIMATED = ("Povijesni brojevi označeni kao procijenjeni izračunati su iz DZS stope nezaposlenosti i aktivnog "
                  "stanovništva. Izravno objavljeni brojevi imaju prednost.")


def labour_market_forecast(data: CountyForecastDTO) -> CountyForecastViewDTO:
    county = data.counties[0]
    reason = county.unavailable_reason or data.unavailable_reason
    if reason == "not_enough_history":
        unavailable = ("Za prognozu je potrebno najmanje 8 punih tjedana praćenja HZZ oglasa. Nastavite prikupljati podatke."
                       if data.target == "job_ads" else
                       "Za prognozu su potrebna najmanje 24 mjeseca s poznatim DZS vrijednostima.")
    else:
        unavailable = UNAVAILABLE.get(reason)
    notes = [NOTE_MODEL, NOTE_INTERVAL]
    if data.target == "job_ads":
        notes.append("Broje se novi oglasi po tjednu objave, uključujući istekle. Jedan oglas može tražiti više radnika.")
    else:
        if data.last_observed_period is not None:
            notes.append(f"Zadnji DZS mjesec: {month_label(data.last_observed_period)} Prognoza počinje sljedećim "
                         "mjesecom, koji zbog kašnjenja objave već može biti u prošlosti.")
        if data.target == "unemployment_rate":
            notes.append("Promjena stope izražena je u postotnim bodovima (p. b.).")
        if any(point.is_estimated for point in county.history):
            notes.append(NOTE_ESTIMATED)
        if any(point.is_provisional for point in county.history):
            notes.append(PROVISIONAL_NOTE)
    sex = {"women": " · žene", "men": " · muškarci"}.get(data.sex, "")
    return CountyForecastViewDTO(
        **data.model_dump(), title=TITLES[data.target],
        description=f"{county.name}{sex} · {'po mjesecima' if data.frequency == 'month' else 'po tjednima'}",
        unavailable_label=unavailable, source_links=source_links(data.sources), view_notes=tuple(notes),
    )
