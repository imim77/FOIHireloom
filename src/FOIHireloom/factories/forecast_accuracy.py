from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.integrations.concrete.chronos import ChronosForecaster
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.concrete.county_resolver import CountyResolver
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.forecast_accuracy import ForecastAccuracyService
from FOIHireloom.services.concrete.labour_forecast_series import NOTE_RATE, DzsSeriesLoader
from FOIHireloom.services.interfaces.forecast_accuracy import ForecastAccuracyServiceInterface


class ForecastAccuracyServiceFactory:
    """ForecastAccuracyServiceFactory assembles backtests with the live forecast's rate loader and model settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, uow_factory: UnitOfWorkFactory,
               forecaster: TimeSeriesForecasterInterface | None = None) -> ForecastAccuracyServiceInterface:
        return ForecastAccuracyService(
            uow_factory, CountyResolver(CroatianCountyCatalog()),
            DzsSeriesLoader("unemployment_rate", "percent", 1, 100.0, (NOTE_RATE,)),
            forecaster if forecaster is not None else ChronosForecaster(self._settings.CHRONOS_MODEL,
                                                                       self._settings.CHRONOS_DEVICE),
        )
