import hashlib
import json
import math
from datetime import date
from importlib.metadata import PackageNotFoundError, version

from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.dto.county_indicators import SourceDTO
from FOIHireloom.dto.forecast_accuracy import (
    CountyForecastAccuracyDTO,
    ForecastAccuracyPointDTO,
    ForecastAccuracyReportDTO,
    ForecastAccuracyRequestDTO,
    ForecastAccuracyWindowDTO,
    ForecastHorizonAccuracyDTO,
)
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.interfaces.forecast_accuracy import ForecastAccuracyServiceInterface

from .county_indicators import add_months
from .county_resolver import CountyResolver
from .forecast_accuracy_calculation import accuracy_metrics, rate_predictions
from .labour_forecast_series import MAX_CONTEXT_MONTHS, CountySeries, DzsSeriesLoader

NOTES = (
    "This retrospective backtest uses the latest stored DZS values, which may have been revised. "
    "It does not reconstruct what was published or available at the historical cutoff.",
    "Only unemployment_rate is evaluated. Future months are withheld from each model input. "
    "The pretrained model's original training data is not controlled by this backtest.",
    "Origins move forward one month. Test windows may overlap; observations count origin/target pairs, "
    "not independent months. Overall scores weight every scored pair equally.",
    "Every scored window has at least 24 known training months, a known final training value, "
    "and complete actual and prior-year baseline values. Incomplete windows are reported as skipped.",
    "MAE and interval width are percentage points. Seasonal naive repeats the same month's value from the "
    "previous year. Both forecasts are scored on exactly the same observations.",
    "Coverage is the fraction of actual values within the nominal 80% interval. It is not an accuracy percentage. "
    "A small sample is not evidence that intervals are calibrated.",
    "Forecast rates use the same [0, 100] bounds and one-decimal precision as the user-facing forecast. "
    "mae_skill is undefined when the seasonal baseline has zero MAE.",
)


class ForecastAccuracyService(ForecastAccuracyServiceInterface):
    """ForecastAccuracyService evaluates monthly rate forecasts on one snapshot with isolated training prefixes.

    Supply the same rate loader and forecaster contract as live forecasts.
    Each origin batches its eligible counties; database resources are released
    before model inference, and missing windows never produce fabricated scores.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, counties: CountyResolver,
                 loader: DzsSeriesLoader, forecaster: TimeSeriesForecasterInterface) -> None:
        self._uow_factory = uow_factory
        self._counties = counties
        self._loader = loader
        self._forecaster = forecaster

    async def evaluate(self, request: ForecastAccuracyRequestDTO) -> ForecastAccuracyReportDTO:
        async with self._uow_factory() as work:
            counties = await self._counties.resolve(work, request.counties)
            generated_at = await work.transaction_time()
            provenance = await work.dzs_imports.get_latest_succeeded()
            # Earlier origins still receive the full context a live forecast
            # would have, even when more than ten years of data is stored.
            series = await self._loader.load(
                work, counties, request.sex, end_period=request.end_period,
                context_months=MAX_CONTEXT_MONTHS + request.horizon + request.windows - 1,
            )
        latest = series.latest_source_period
        end = request.end_period or latest
        if latest is not None and (end > latest or end < series.periods[0]):
            raise InvalidIndicatorRequestError(
                f"Choose an end month between {series.periods[0]:%Y-%m} and {latest:%Y-%m}, not {end:%Y-%m}.")
        windows: dict[int, list[ForecastAccuracyWindowDTO]] = {county.id: [] for county in counties}
        for offset in reversed(range(request.windows)):
            if end is None:
                break
            cutoff = add_months(end, -request.horizon - offset)
            eligible = []
            training = []
            for county in counties:
                window, history = self._window(series, county.id, cutoff, request.horizon)
                windows[county.id].append(window)
                if window.unavailable_reason is None:
                    eligible.append(county)
                    training.append([math.nan if value is None else value for value in history])
            if not eligible:
                continue
            predictions = await self._forecaster.forecast(training, request.horizon)
            if len(predictions) != len(eligible):
                raise ForecastUnavailableError("The forecasting model returned the wrong number of series; no accuracy was scored.")
            for county, prediction in zip(eligible, predictions, strict=True):
                window = windows[county.id][-1]
                quantiles = rate_predictions(prediction, request.horizon)
                values = dict(zip(series.periods, series.values[county.id], strict=True))
                provisional = dict(zip(series.periods, series.provisional[county.id], strict=True))
                points = tuple(
                    ForecastAccuracyPointDTO(
                        period=period, step=step, actual=values[period], low=low, median=median, high=high,
                        seasonal_naive=values[add_months(period, -12)], is_provisional=bool(provisional[period]),
                    )
                    for step, (low, median, high) in enumerate(quantiles, start=1)
                    for period in (add_months(cutoff, step),)
                )
                windows[county.id][-1] = window.model_copy(update={"points": points, "metrics": accuracy_metrics(points)})
        results = tuple(
            CountyForecastAccuracyDTO(
                code=county.code, name=county.name, iso_code=county.iso_code, windows=tuple(windows[county.id]),
                metrics=accuracy_metrics([point for window in windows[county.id] for point in window.points]),
            ) for county in counties
        )
        points = [point for county in results for window in county.windows for point in window.points]
        evaluated = sum(bool(window.points) for county in results for window in county.windows)
        return ForecastAccuracyReportDTO(
            generated_at=generated_at, request=request, status="evaluated" if points else "unavailable",
            model=self._forecaster.model_name, end_period=end, latest_source_period=latest,
            source_unavailable_reason=series.unavailable_reason,
            dataset_sha256=dataset_hash(series), package_versions=package_versions(), dzs=provenance,
            evaluated_windows=evaluated, skipped_windows=len(counties) * request.windows - evaluated,
            metrics=accuracy_metrics(points), counties=results,
            by_horizon=tuple(ForecastHorizonAccuracyDTO(step=step, metrics=accuracy_metrics(
                [point for point in points if point.step == step])) for step in range(1, request.horizon + 1)),
            sources=(*series.sources, SourceDTO(name=f"Amazon Chronos ({self._forecaster.model_name})",
                     url=f"https://huggingface.co/{self._forecaster.model_name}", description="Forecast model")),
            notes=(*NOTES, *([f"No evaluable source series: {series.unavailable_reason}."] if series.unavailable_reason else [])),
        )

    def _window(self, series: CountySeries, county_id: int, cutoff: date,
                horizon: int) -> tuple[ForecastAccuracyWindowDTO, list[float | None]]:
        values = dict(zip(series.periods, series.values.get(county_id, []), strict=True))
        first_context = add_months(cutoff, 1 - MAX_CONTEXT_MONTHS)
        past = [period for period in series.periods if first_context <= period <= cutoff]
        first = next((period for period in past if values[period] is not None), None)
        periods = [period for period in past if first is not None and period >= first]
        history = [values[period] for period in periods]
        known = sum(value is not None for value in history)
        test = [add_months(cutoff, step) for step in range(1, horizon + 1)]
        reason = series.unavailable_reason
        if reason is None:
            if known < self._loader.min_history:
                reason = "not_enough_history"
            elif values.get(cutoff) is None:
                reason = "missing_training_endpoint"
            elif any(values.get(period) is None for period in test):
                reason = "missing_actuals"
            elif any(values.get(add_months(period, -12)) is None for period in test):
                reason = "missing_seasonal_baseline"
        return ForecastAccuracyWindowDTO(
            cutoff=cutoff, training_first_period=first, training_periods=len(history), training_known_values=known,
            unavailable_reason=reason, points=(), metrics=accuracy_metrics(()),
        ), history


def dataset_hash(series: CountySeries) -> str:
    """Hash the exact snapshot used for this run, including missing and provisional values."""
    document = {"periods": [period.isoformat() for period in series.periods],
                "values": series.values, "provisional": series.provisional}
    return hashlib.sha256(json.dumps(document, sort_keys=True, allow_nan=False).encode()).hexdigest()


def package_versions() -> dict[str, str]:
    installed = {}
    for package in ("chronos-forecasting", "torch", "transformers", "foihireloom"):
        try:
            installed[package] = version(package)
        except PackageNotFoundError:
            pass
    return installed
