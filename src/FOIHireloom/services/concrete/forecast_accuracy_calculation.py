import math
from collections.abc import Sequence

from FOIHireloom.dto.forecast import QuantileForecastDTO
from FOIHireloom.dto.forecast_accuracy import ForecastAccuracyMetricsDTO, ForecastAccuracyPointDTO
from FOIHireloom.exceptions import ForecastUnavailableError


def rate_predictions(prediction: QuantileForecastDTO, horizon: int) -> list[tuple[float, float, float]]:
    """Validate raw quantiles, then apply the same rate bounds and precision as the user-facing forecast."""
    if any(len(values) != horizon for values in (prediction.low, prediction.median, prediction.high)):
        raise ForecastUnavailableError("The forecasting model returned an incomplete forecast; no accuracy was scored.")
    points = list(zip(prediction.low, prediction.median, prediction.high, strict=True))
    if any(not all(math.isfinite(value) for value in point) or not point[0] <= point[1] <= point[2] for point in points):
        raise ForecastUnavailableError("The forecasting model returned invalid quantiles; no accuracy was scored.")
    return [tuple(round(min(100.0, max(0.0, value)), 1) for value in point) for point in points]


def accuracy_metrics(points: Sequence[ForecastAccuracyPointDTO]) -> ForecastAccuracyMetricsDTO:
    """Calculate paired errors and interval coverage without rounding before aggregation."""
    count = len(points)
    mae = math.fsum(abs(point.median - point.actual) for point in points) / count if count else None
    baseline = math.fsum(abs(point.seasonal_naive - point.actual) for point in points) / count if count else None
    return ForecastAccuracyMetricsDTO(
        observations=count, provisional_observations=sum(point.is_provisional for point in points),
        mae_pp=mae, seasonal_naive_mae_pp=baseline,
        mae_skill=1 - mae / baseline if baseline else None,
        interval_coverage=sum(point.low <= point.actual <= point.high for point in points) / count if count else None,
        mean_interval_width_pp=math.fsum(point.high - point.low for point in points) / count if count else None,
    )
