import math
from collections.abc import Callable, Mapping

from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import SourceDTO
from FOIHireloom.dto.forecast import (
    MAX_FORECAST_COUNTIES,
    CountyForecastDTO,
    CountyForecastRequestDTO,
    CountyForecastSeriesDTO,
    ForecastTarget,
    ObservedPointDTO,
    PredictedPointDTO,
    QuantileForecastDTO,
)
from FOIHireloom.exceptions import InvalidIndicatorRequestError
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface

from .county_resolver import CountyResolver
from .labour_forecast_series import CountySeries, CountySeriesLoader

NOTE_MODEL = ("Forecasts come from Amazon Chronos, a pretrained time-series model that continues each county's past "
              "series. It knows nothing about policy changes, economic shocks or other events after the last "
              "observed period, so treat the result as a trend estimate, not a prediction of what will happen.")
NOTE_INTERVAL = ("median is the central forecast; low and high bound an 80% interval (10th and 90th percentile). "
                 "Report the interval with the median, and note that it widens further ahead.")


class LabourMarketForecastService(LabourMarketForecastServiceInterface):
    """LabourMarketForecastService forecasts county series with a time-series model, one loader per target.

    Loaders supply the past values and the target's limits; this service
    resolves counties, leaves out counties with too short a series, asks the
    model once for all others and keeps forecasts within the unit's range
    (no negative counts, no rate above 100%).
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        counties: CountyResolver,
        forecaster: TimeSeriesForecasterInterface,
        loaders: Mapping[ForecastTarget, CountySeriesLoader],
    ) -> None:
        self._uow_factory = uow_factory
        self._counties = counties
        self._forecaster = forecaster
        self._loaders = loaders

    async def forecast(self, request: CountyForecastRequestDTO) -> CountyForecastDTO:
        loader = self._loaders[request.target]
        self._counties.check_count(request.counties, 1, MAX_FORECAST_COUNTIES)
        horizon = request.horizon or loader.default_horizon
        if not 1 <= horizon <= loader.max_horizon:
            raise InvalidIndicatorRequestError(
                f"Choose a horizon of 1 to {loader.max_horizon} {loader.frequency}s for {request.target}, "
                f"not {horizon}.")
        async with self._uow_factory() as work:
            counties = await self._counties.resolve(work, request.counties)
            series = await loader.load(work, counties, request.sex)
        histories = {county.id: trimmed(series.values.get(county.id, [])) for county in counties}
        usable = [county for county in counties
                  if series.unavailable_reason is None and known(histories[county.id]) >= loader.min_history]
        predicted = await self._forecaster.forecast(
            [[math.nan if value is None else value for value in histories[county.id]] for county in usable], horizon)
        forecasts = dict(zip((county.id for county in usable), predicted, strict=True))
        last = series.periods[-1] if series.periods and series.unavailable_reason is None else None
        return CountyForecastDTO(
            target=request.target, frequency=loader.frequency, unit=loader.unit,
            sex=request.sex if loader.uses_sex else None, horizon=horizon, model=self._forecaster.model_name,
            last_observed_period=last,
            counties=tuple(self._county(loader, county, series, forecasts.get(county.id), horizon)
                           for county in counties),
            unavailable_reason=series.unavailable_reason,
            sources=(*series.sources, self._model_source()),
            notes=(NOTE_MODEL, NOTE_INTERVAL, *loader.notes),
        )

    def _county(
        self, loader: CountySeriesLoader, county: CountyDTO, series: CountySeries,
        forecast: QuantileForecastDTO | None, horizon: int,
    ) -> CountyForecastSeriesDTO:
        values = series.values.get(county.id, [])
        provisional = series.provisional.get(county.id, [None] * len(values))
        estimated = series.estimated.get(county.id, [None] * len(values))
        shown = slice(-loader.shown_history, None)
        history = tuple(
            ObservedPointDTO(period=period, value=None if value is None else rounded(value, loader.digits),
                             is_provisional=flag, is_estimated=guess)
            for period, value, flag, guess in zip(series.periods[shown], values[shown], provisional[shown],
                                                  estimated[shown], strict=True)
        )
        last_observed = next((point for point in reversed(history) if point.value is not None), None)
        if forecast is None:
            reason = series.unavailable_reason or "not_enough_history"
            return CountyForecastSeriesDTO(
                code=county.code, name=county.name, iso_code=county.iso_code, history=history, forecast=(),
                last_observed=last_observed, change_to_horizon=None, unavailable_reason=reason)
        bound = self._bound(loader)
        predicted = tuple(
            PredictedPointDTO(period=loader.after(series.periods[-1], step + 1), median=bound(median),
                              low=bound(low), high=bound(high))
            for step, (low, median, high) in enumerate(zip(forecast.low, forecast.median, forecast.high, strict=True))
        )
        change = (None if last_observed is None or last_observed.value is None
                  else rounded(predicted[-1].median - last_observed.value, loader.digits))
        return CountyForecastSeriesDTO(
            code=county.code, name=county.name, iso_code=county.iso_code, history=history, forecast=predicted,
            last_observed=last_observed, change_to_horizon=change, unavailable_reason=None)

    @staticmethod
    def _bound(loader: CountySeriesLoader) -> Callable[[float], float]:
        def bound(value: float) -> float:
            value = max(value, 0.0)
            if loader.upper_bound is not None:
                value = min(value, loader.upper_bound)
            return rounded(value, loader.digits)
        return bound

    def _model_source(self) -> SourceDTO:
        model = self._forecaster.model_name
        return SourceDTO(name=f"Amazon Chronos ({model})", url=f"https://huggingface.co/{model}",
                         description="Pretrained time-series forecasting model that produced the forecasts.")


def trimmed(values: list[float | None]) -> list[float | None]:
    """The values from the first known one on; months before a county's data starts are not gaps."""
    start = next((index for index, value in enumerate(values) if value is not None), len(values))
    return values[start:]


def known(values: list[float | None]) -> int:
    return sum(value is not None for value in values)


def rounded(value: float, digits: int) -> float:
    return float(round(value, digits)) if digits else float(round(value))

