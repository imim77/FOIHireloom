from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.integrations.concrete.chronos import ChronosForecaster
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.concrete.county_resolver import CountyResolver
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.labour_forecast import LabourMarketForecastService
from FOIHireloom.services.concrete.labour_forecast_series import (
    NOTE_PERSONS,
    NOTE_RATE,
    DzsPersonsSeriesLoader,
    DzsSeriesLoader,
    HzzJobAdsSeriesLoader,
)
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface


def unemployment_rate_loader() -> DzsSeriesLoader:
    """The DZS unemployment-rate series as the forecast tools show it, so backtests measure the same series."""
    return DzsSeriesLoader("unemployment_rate", "percent", 1, 100.0, (NOTE_RATE,))


def chronos_forecaster(settings: Settings) -> ChronosForecaster:
    """The configured Chronos model; it loads on its first forecast, not here."""
    return ChronosForecaster(settings.CHRONOS_MODEL, settings.CHRONOS_DEVICE)


class LabourMarketForecastServiceFactory:
    """Assemble the read-only forecast service; the Chronos model loads on its first forecast, not here."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self, uow_factory: UnitOfWorkFactory, forecaster: TimeSeriesForecasterInterface | None = None,
    ) -> LabourMarketForecastServiceInterface:
        forecaster = forecaster or chronos_forecaster(self._settings)
        loaders = {
            "unemployment_rate": unemployment_rate_loader(),
            "unemployed": DzsPersonsSeriesLoader("unemployed", (NOTE_PERSONS,)),
            "employed": DzsPersonsSeriesLoader("employed", (NOTE_PERSONS,)),
            "job_ads": HzzJobAdsSeriesLoader(),
        }
        return LabourMarketForecastService(uow_factory, CountyResolver(CroatianCountyCatalog()), forecaster, loaders)
