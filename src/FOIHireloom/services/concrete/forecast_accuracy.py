import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from importlib.metadata import PackageNotFoundError, version

from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import SourceDTO
from FOIHireloom.dto.dzs import DzsImportProvenanceDTO
from FOIHireloom.dto.forecast import QuantileForecastDTO
from FOIHireloom.dto.forecast_accuracy import (
    AccuracyUnavailableReason,
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


@dataclass(frozen=True)
class TrainingWindow:
    """TrainingWindow holds one county's training prefix and test months for one forecast origin."""

    values: dict[date, float | None]
    cutoff: date
    history: list[float | None]
    test: list[date]

    @property
    def known(self) -> int:
        return sum(value is not None for value in self.history)


type WindowCheck = Callable[[TrainingWindow, int], bool]

WINDOW_CHECKS: tuple[tuple[AccuracyUnavailableReason, WindowCheck], ...] = (
    ("not_enough_history", lambda window, min_history: window.known < min_history),
    ("missing_training_endpoint", lambda window, _: window.values.get(window.cutoff) is None),
    ("missing_actuals", lambda window, _: any(window.values.get(period) is None for period in window.test)),
    ("missing_seasonal_baseline",
     lambda window, _: any(window.values.get(add_months(period, -12)) is None for period in window.test)),
)


@dataclass(frozen=True)
class BacktestSnapshot:
    """BacktestSnapshot holds what one backtest reads in its single transaction."""

    counties: list[CountyDTO]
    generated_at: datetime
    provenance: DzsImportProvenanceDTO | None
    series: CountySeries


type CountyWindows = dict[int, list[ForecastAccuracyWindowDTO]]


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
        snapshot = await self._snapshot(request)
        end = self._end_period(request, snapshot.series)
        windows: CountyWindows = {county.id: [] for county in snapshot.counties}
        if end is not None:
            for offset in reversed(range(request.windows)):
                cutoff = add_months(end, -request.horizon - offset)
                await self._evaluate_origin(snapshot, cutoff, request.horizon, windows)
        return self._report(request, snapshot, end, windows)

    async def _snapshot(self, request: ForecastAccuracyRequestDTO) -> BacktestSnapshot:
        async with self._uow_factory() as work:
            counties = await self._counties.resolve(work, request.counties)
            generated_at = await work.transaction_time()
            provenance = await work.dzs_imports.get_latest_succeeded()
            series = await self._loader.load(
                work, counties, request.sex, end_period=request.end_period,
                context_months=MAX_CONTEXT_MONTHS + request.horizon + request.windows - 1,
            )
        return BacktestSnapshot(counties=counties, generated_at=generated_at, provenance=provenance, series=series)

    @staticmethod
    def _end_period(request: ForecastAccuracyRequestDTO, series: CountySeries) -> date | None:
        """Return the last month scored: the requested one, else the latest stored; raise outside the series."""
        latest = series.latest_source_period
        end = request.end_period or latest
        if latest is not None and (end > latest or end < series.periods[0]):
            raise InvalidIndicatorRequestError(
                f"Choose an end month between {series.periods[0]:%Y-%m} and {latest:%Y-%m}, not {end:%Y-%m}.")
        return end

    async def _evaluate_origin(
        self, snapshot: BacktestSnapshot, cutoff: date, horizon: int, windows: CountyWindows,
    ) -> None:
        """Append each county's window for the origin cutoff, scored when the county is eligible."""
        eligible: list[CountyDTO] = []
        training: list[list[float]] = []
        for county in snapshot.counties:
            window, history = self._window(snapshot.series, county.id, cutoff, horizon)
            windows[county.id].append(window)
            if window.unavailable_reason is None:
                eligible.append(county)
                training.append([math.nan if value is None else value for value in history])
        if not eligible:
            return
        predictions = await self._forecaster.forecast(training, horizon)
        if len(predictions) != len(eligible):
            raise ForecastUnavailableError("The forecasting model returned the wrong number of series; no accuracy was scored.")
        for county, prediction in zip(eligible, predictions, strict=True):
            windows[county.id][-1] = self._scored(windows[county.id][-1], snapshot.series, county.id, prediction,
                                                  horizon)

    @staticmethod
    def _scored(window: ForecastAccuracyWindowDTO, series: CountySeries, county_id: int,
                prediction: QuantileForecastDTO, horizon: int) -> ForecastAccuracyWindowDTO:
        """Return the window with the prediction paired with the actual and seasonal naive values."""
        quantiles = rate_predictions(prediction, horizon)
        values = dict(zip(series.periods, series.values[county_id], strict=True))
        provisional = dict(zip(series.periods, series.provisional[county_id], strict=True))
        points = tuple(
            ForecastAccuracyPointDTO(
                period=period, step=step, actual=values[period], low=low, median=median, high=high,
                seasonal_naive=values[add_months(period, -12)], is_provisional=bool(provisional[period]),
            )
            for step, (low, median, high) in enumerate(quantiles, start=1)
            for period in (add_months(window.cutoff, step),)
        )
        return window.model_copy(update={"points": points, "metrics": accuracy_metrics(points)})

    def _window(self, series: CountySeries, county_id: int, cutoff: date,
                horizon: int) -> tuple[ForecastAccuracyWindowDTO, list[float | None]]:
        """Return the county's unscored window for the origin cutoff and its training values."""
        values = dict(zip(series.periods, series.values.get(county_id, []), strict=True))
        first_context = add_months(cutoff, 1 - MAX_CONTEXT_MONTHS)
        past = [period for period in series.periods if first_context <= period <= cutoff]
        first = next((period for period in past if values[period] is not None), None)
        periods = [period for period in past if first is not None and period >= first]
        training = TrainingWindow(values=values, cutoff=cutoff, history=[values[period] for period in periods],
                                  test=[add_months(cutoff, step) for step in range(1, horizon + 1)])
        return ForecastAccuracyWindowDTO(
            cutoff=cutoff, training_first_period=first, training_periods=len(training.history),
            training_known_values=training.known, unavailable_reason=self._skip_reason(series, training),
            points=(), metrics=accuracy_metrics(()),
        ), training.history

    def _skip_reason(self, series: CountySeries, training: TrainingWindow) -> AccuracyUnavailableReason | None:
        """Return why the window cannot be scored, the source's reason first, or None to score it."""
        if series.unavailable_reason is not None:
            return series.unavailable_reason
        return next((reason for reason, fails in WINDOW_CHECKS if fails(training, self._loader.min_history)), None)

    def _report(self, request: ForecastAccuracyRequestDTO, snapshot: BacktestSnapshot, end: date | None,
                windows: CountyWindows) -> ForecastAccuracyReportDTO:
        series = snapshot.series
        results = tuple(self._county_result(county, windows[county.id]) for county in snapshot.counties)
        points = [point for county in results for window in county.windows for point in window.points]
        evaluated = sum(bool(window.points) for county in results for window in county.windows)
        return ForecastAccuracyReportDTO(
            generated_at=snapshot.generated_at, request=request, status="evaluated" if points else "unavailable",
            model=self._forecaster.model_name, end_period=end, latest_source_period=series.latest_source_period,
            source_unavailable_reason=series.unavailable_reason,
            dataset_sha256=dataset_hash(series), package_versions=package_versions(), dzs=snapshot.provenance,
            evaluated_windows=evaluated, skipped_windows=len(snapshot.counties) * request.windows - evaluated,
            metrics=accuracy_metrics(points), counties=results, by_horizon=by_horizon(points, request.horizon),
            sources=(*series.sources, self._model_source()), notes=report_notes(series),
        )

    @staticmethod
    def _county_result(county: CountyDTO, windows: Sequence[ForecastAccuracyWindowDTO]) -> CountyForecastAccuracyDTO:
        return CountyForecastAccuracyDTO(
            code=county.code, name=county.name, iso_code=county.iso_code, windows=tuple(windows),
            metrics=accuracy_metrics([point for window in windows for point in window.points]),
        )

    def _model_source(self) -> SourceDTO:
        model = self._forecaster.model_name
        return SourceDTO(name=f"Amazon Chronos ({model})", url=f"https://huggingface.co/{model}",
                         description="Forecast model")


def by_horizon(points: Sequence[ForecastAccuracyPointDTO], horizon: int) -> tuple[ForecastHorizonAccuracyDTO, ...]:
    """Score every step ahead on its own, so a widening error is visible."""
    return tuple(ForecastHorizonAccuracyDTO(step=step, metrics=accuracy_metrics(
        [point for point in points if point.step == step])) for step in range(1, horizon + 1))


def report_notes(series: CountySeries) -> tuple[str, ...]:
    if series.unavailable_reason is None:
        return NOTES
    return (*NOTES, f"No evaluable source series: {series.unavailable_reason}.")


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
