"""County forecasts of DZS labour-market values and HZZ job ads, made by a pretrained time-series model.

Every predicted value comes with an 80% interval: low and high are the 10th
and 90th percentile of the model's forecast distribution, median the 50th.
A county whose series is too short or missing gets no forecast and a
machine-readable reason instead, never a guessed value.
"""

from datetime import date
from typing import Literal

from .base import ModelConfigBaseModel
from .county_indicators import SourceDTO
from .dzs import DzsSex

# unemployment_rate, unemployed and employed are DZS monthly county values;
# job_ads counts new HZZ advertisements per publication week.
type ForecastTarget = Literal["unemployment_rate", "unemployed", "employed", "job_ads"]
type ForecastFrequency = Literal["month", "week"]
type ForecastUnit = Literal["percent", "persons", "ads"]

# no_dzs_data: no DZS import has succeeded. no_common_period: no month has a
# known value for every requested county. no_hzz_data: no HZZ job has been
# stored yet. not_enough_history: the county has fewer known past values
# than the model needs for a meaningful forecast.
type ForecastUnavailableReason = Literal["no_dzs_data", "no_common_period", "no_hzz_data", "not_enough_history"]

QUANTILE_LEVELS = (0.1, 0.5, 0.9)
INTERVAL = 0.8  # Share of outcomes the model expects between low and high.
MAX_FORECAST_COUNTIES = 6


class CountyForecastRequestDTO(ModelConfigBaseModel):
    """What to forecast for 1 to 6 counties; horizon None takes the target's default."""

    counties: tuple[str, ...]
    target: ForecastTarget
    horizon: int | None = None
    sex: DzsSex = "total"


class QuantileForecastDTO(ModelConfigBaseModel):
    """One series' forecast as the model returns it, one value per future step."""

    low: tuple[float, ...]
    median: tuple[float, ...]
    high: tuple[float, ...]


class WeeklyJobAdsRowDTO(ModelConfigBaseModel):
    """New HZZ ads of one county published in the week starting on week (a Monday)."""

    county_id: int
    week: date
    jobs: int


class ObservedPointDTO(ModelConfigBaseModel):
    """A past value; value is None when the source has none for that period."""

    period: date
    value: float | None
    is_provisional: bool | None = None


class PredictedPointDTO(ModelConfigBaseModel):
    period: date
    median: float
    low: float
    high: float


class CountyForecastSeriesDTO(ModelConfigBaseModel):
    """One county's recent history and forecast.

    change_to_horizon is the median at the last forecast period minus the
    last observed value, in the target's unit (percentage points for a rate).
    """

    code: str
    name: str
    iso_code: str
    history: tuple[ObservedPointDTO, ...]
    forecast: tuple[PredictedPointDTO, ...]
    last_observed: ObservedPointDTO | None
    change_to_horizon: float | None
    unavailable_reason: ForecastUnavailableReason | None


class CountyForecastDTO(ModelConfigBaseModel):
    """Forecasts of one target for the requested counties, in the requested order.

    Periods are first days of months, or Mondays of weeks. The forecast
    starts in the period after the last one the source has for every
    county, which may already lie in the past for DZS.
    """

    target: ForecastTarget
    frequency: ForecastFrequency
    unit: ForecastUnit
    sex: DzsSex | None
    horizon: int
    interval: float = INTERVAL
    model: str
    last_observed_period: date | None
    counties: tuple[CountyForecastSeriesDTO, ...]
    unavailable_reason: ForecastUnavailableReason | None
    sources: tuple[SourceDTO, ...]
    notes: tuple[str, ...]
