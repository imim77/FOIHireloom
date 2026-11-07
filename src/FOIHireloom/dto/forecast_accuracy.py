"""Retrospective accuracy of monthly county unemployment-rate forecasts."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from .base import ModelConfigBaseModel
from .county_indicators import SourceDTO
from .dzs import DzsImportProvenanceDTO, DzsSex

type AccuracyUnavailableReason = Literal[
    "no_dzs_data", "no_common_period", "not_enough_history", "missing_training_endpoint",
    "missing_actuals", "missing_seasonal_baseline",
]


class ForecastAccuracyRequestDTO(ModelConfigBaseModel):
    """ForecastAccuracyRequestDTO selects monthly rolling origins ending at or before end_period."""

    counties: Annotated[tuple[Annotated[str, Field(min_length=1, max_length=100)], ...], Field(min_length=1, max_length=21)]
    horizon: int = Field(default=6, ge=1, le=12)
    windows: int = Field(default=3, ge=1, le=12)
    sex: DzsSex = "total"
    end_period: date | None = Field(default=None, ge=date(1900, 1, 1))

    @field_validator("end_period")
    @classmethod
    def require_month_start(cls, value: date | None) -> date | None:
        if value is not None and value.day != 1:
            raise ValueError("end_period must be the first day of a month.")
        return value


class ForecastAccuracyMetricsDTO(ModelConfigBaseModel):
    """ForecastAccuracyMetricsDTO scores paired Chronos and seasonal forecasts; errors are percentage points.

    Coverage is a fraction in [0, 1]. mae_skill is 1 - MAE / baseline MAE,
    positive when Chronos improves on the baseline; None if baseline MAE is zero.
    Empty samples have null metrics, never a perfect zero score.
    """

    observations: int
    provisional_observations: int
    mae_pp: float | None
    seasonal_naive_mae_pp: float | None
    mae_skill: float | None
    interval_coverage: float | None
    mean_interval_width_pp: float | None


class ForecastAccuracyPointDTO(ModelConfigBaseModel):
    period: date
    step: int
    actual: float
    median: float
    low: float
    high: float
    seasonal_naive: float
    is_provisional: bool


class ForecastAccuracyWindowDTO(ModelConfigBaseModel):
    cutoff: date
    training_first_period: date | None
    training_periods: int
    training_known_values: int
    unavailable_reason: AccuracyUnavailableReason | None
    points: tuple[ForecastAccuracyPointDTO, ...]
    metrics: ForecastAccuracyMetricsDTO


class CountyForecastAccuracyDTO(ModelConfigBaseModel):
    code: str
    name: str
    iso_code: str
    windows: tuple[ForecastAccuracyWindowDTO, ...]
    metrics: ForecastAccuracyMetricsDTO


class ForecastHorizonAccuracyDTO(ModelConfigBaseModel):
    step: int
    metrics: ForecastAccuracyMetricsDTO


class ForecastAccuracyReportDTO(ModelConfigBaseModel):
    generated_at: datetime
    request: ForecastAccuracyRequestDTO
    target: Literal["unemployment_rate"] = "unemployment_rate"
    status: Literal["evaluated", "unavailable"]
    model: str
    interval: float = 0.8
    baseline: Literal["seasonal_naive_12"] = "seasonal_naive_12"
    evaluation_basis: Literal["latest_revised_data"] = "latest_revised_data"
    end_period: date | None
    latest_source_period: date | None
    source_unavailable_reason: AccuracyUnavailableReason | None
    dataset_sha256: str
    package_versions: dict[str, str]
    dzs: DzsImportProvenanceDTO | None
    evaluated_windows: int
    skipped_windows: int
    metrics: ForecastAccuracyMetricsDTO
    by_horizon: tuple[ForecastHorizonAccuracyDTO, ...]
    counties: tuple[CountyForecastAccuracyDTO, ...]
    sources: tuple[SourceDTO, ...]
    notes: tuple[str, ...]
