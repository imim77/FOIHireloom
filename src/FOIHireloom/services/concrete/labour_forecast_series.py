"""The past series a labour-market forecast extends, one loader per data source.

Each loader returns every requested county's values on one shared timeline,
so the model sees comparable series and the forecasts start together.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import SourceDTO
from FOIHireloom.dto.dzs import DzsIndicator, DzsSex
from FOIHireloom.dto.forecast import ForecastFrequency, ForecastUnavailableReason, ForecastUnit
from FOIHireloom.domain.job_search import local_date

from .county_indicators import HZZ_SOURCE, add_months, sources

MAX_CONTEXT_MONTHS = 120  # DZS county series start in 2020; older months add little for the model.
MAX_CONTEXT_WEEKS = 156

NOTE_DZS_PERIOD = ("The forecast starts in the month after the latest DZS month known for every requested county. "
                   "DZS publishes with a delay, so the first forecast months may already be over; DZS values for "
                   "months of 2026 are provisional (is_provisional).")
NOTE_RATE = ("unemployment_rate is the registered unemployment rate in percent; change_to_horizon is in percentage "
             "points.")
NOTE_PERSONS = "unemployed and employed count persons, as DZS publishes them per county."
NOTE_JOB_ADS = ("job_ads counts new HZZ advertisements by publication week (weeks start on Monday), whether or not "
                "they are still open; one ad may seek several workers, so it is not a count of workers. The series "
                "starts with the first full week after this server began storing HZZ ads and ends with the last "
                "full week, so it may be short and its forecast uncertain.")


@dataclass(frozen=True)
class CountySeries:
    """Past values of one target on a shared timeline, oldest first; None marks a missing value."""

    periods: tuple[date, ...]
    values: dict[int, list[float | None]] = field(default_factory=dict)  # By county ID, aligned with periods.
    provisional: dict[int, list[bool | None]] = field(default_factory=dict)
    unavailable_reason: ForecastUnavailableReason | None = None
    sources: tuple[SourceDTO, ...] = ()


class CountySeriesLoader(ABC):
    """CountySeriesLoader reads one forecast target's past values and says how to read them.

    The class attributes describe the target for users and set the limits
    the service enforces: how far ahead to forecast and how much history a
    county needs before the model is asked at all.
    """

    frequency: ForecastFrequency
    unit: ForecastUnit
    digits: int  # Decimals of the values reported.
    upper_bound: float | None = None
    default_horizon: int
    max_horizon: int
    min_history: int  # Known past values a county needs for a forecast.
    shown_history: int  # Past periods reported next to the forecast.
    uses_sex: bool
    notes: tuple[str, ...]

    @abstractmethod
    async def load(self, work: UnitOfWork, counties: Sequence[CountyDTO], sex: DzsSex) -> CountySeries:
        """Return the counties' past values within the caller's transaction."""

    @abstractmethod
    def after(self, period: date, steps: int) -> date:
        """Return the period steps periods after period."""


class DzsSeriesLoader(CountySeriesLoader):
    """DzsSeriesLoader reads a monthly DZS county indicator up to the latest month known for every county."""

    frequency = "month"
    default_horizon = 12
    max_horizon = 24
    min_history = 24  # Two years, so the model can see the seasonal pattern at least twice.
    shown_history = 24
    uses_sex = True

    def __init__(self, indicator: DzsIndicator, unit: ForecastUnit, digits: int, upper_bound: float | None,
                 notes: tuple[str, ...]) -> None:
        self._indicator = indicator
        self.unit = unit
        self.digits = digits
        self.upper_bound = upper_bound
        self.notes = (NOTE_DZS_PERIOD, *notes)

    async def load(self, work: UnitOfWork, counties: Sequence[CountyDTO], sex: DzsSex) -> CountySeries:
        ids = tuple(county.id for county in counties)
        provenance = await work.dzs_imports.get_latest_succeeded()
        if provenance is None:
            return CountySeries(periods=(), unavailable_reason="no_dzs_data")
        found = sources(provenance, with_hzz=False)
        last = (await work.dzs_indicator_values.latest_common_periods(ids, (self._indicator,), sex)).get(
            self._indicator)
        if last is None:
            return CountySeries(periods=(), unavailable_reason="no_common_period", sources=found)
        first = add_months(last, 1 - MAX_CONTEXT_MONTHS)
        stored = await work.dzs_indicator_values.list_series(ids, self._indicator, sex, first, last)
        by_key = {(value.county_id, value.period): value for value in stored}
        periods = tuple(add_months(first, offset) for offset in range(MAX_CONTEXT_MONTHS))
        values: dict[int, list[float | None]] = {}
        provisional: dict[int, list[bool | None]] = {}
        for county_id in ids:
            points = [by_key.get((county_id, period)) for period in periods]
            values[county_id] = [None if p is None or p.value is None else float(p.value) for p in points]
            provisional[county_id] = [None if p is None or p.value is None else p.is_provisional for p in points]
        return CountySeries(periods=periods, values=values, provisional=provisional, sources=found)

    def after(self, period: date, steps: int) -> date:
        return add_months(period, steps)


class HzzJobAdsSeriesLoader(CountySeriesLoader):
    """HzzJobAdsSeriesLoader counts new HZZ ads per county and full week since the server began storing them.

    The first week after storage began is left out: ads that closed before
    the first sync were never seen, so earlier weeks would look too quiet.
    """

    frequency = "week"
    unit = "ads"
    digits = 0
    default_horizon = 8
    max_horizon = 26
    min_history = 8
    shown_history = 26
    uses_sex = False
    notes = (NOTE_JOB_ADS,)

    async def load(self, work: UnitOfWork, counties: Sequence[CountyDTO], sex: DzsSex) -> CountySeries:
        started = await work.jobs.tracking_started_at()
        if started is None:
            return CountySeries(periods=(), unavailable_reason="no_hzz_data", sources=(HZZ_SOURCE,))
        today = local_date(await work.transaction_time())
        last = monday(today) - timedelta(weeks=1)  # The current week is not over yet.
        first = max(monday(local_date(started)) + timedelta(weeks=1), last - timedelta(weeks=MAX_CONTEXT_WEEKS - 1))
        weeks = max(0, (last - first).days // 7 + 1)
        periods = tuple(first + timedelta(weeks=offset) for offset in range(weeks))
        ids = tuple(county.id for county in counties)
        rows = await work.jobs.weekly_published_counts(ids, first, last) if periods else []
        counts = {(row.county_id, row.week): row.jobs for row in rows}
        # A week without ads is a known 0: the feeds were read, nothing was published.
        values: dict[int, list[float | None]] = {
            county_id: [float(counts.get((county_id, week), 0)) for week in periods] for county_id in ids}
        return CountySeries(periods=periods, values=values, sources=(HZZ_SOURCE,))

    def after(self, period: date, steps: int) -> date:
        return period + timedelta(weeks=steps)


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())
