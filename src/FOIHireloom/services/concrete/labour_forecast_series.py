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
NOTE_PERSONS = "unemployed and employed count persons per county."
NOTE_ESTIMATED = ("DZS publishes exact unemployed and employed counts only for the months of its latest release. "
                  "Other months (is_estimated) are estimated from the registered unemployment rate and the active "
                  "population: unemployed = rate x active population / 100, employed = active population - "
                  "unemployed. The rate has one decimal, so an estimate may be off by up to 0.05% of the active "
                  "population; say that these counts are estimates.")
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
    estimated: dict[int, list[bool | None]] = field(default_factory=dict)
    unavailable_reason: ForecastUnavailableReason | None = None
    sources: tuple[SourceDTO, ...] = ()
    latest_source_period: date | None = None


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


@dataclass(frozen=True)
class MonthValue:
    value: float
    is_provisional: bool
    is_estimated: bool = False


type MonthValues = dict[tuple[int, date], MonthValue]  # By county ID and month.


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

    async def load(self, work: UnitOfWork, counties: Sequence[CountyDTO], sex: DzsSex, *,
                   end_period: date | None = None, context_months: int = MAX_CONTEXT_MONTHS) -> CountySeries:
        ids = tuple(county.id for county in counties)
        provenance = await work.dzs_imports.get_latest_succeeded()
        if provenance is None:
            return CountySeries(periods=(), unavailable_reason="no_dzs_data")
        found = sources(provenance, with_hzz=False)
        last = await self._last_period(work, ids, sex)
        if last is None:
            return CountySeries(periods=(), unavailable_reason="no_common_period", sources=found)
        latest = last
        last = min(last, end_period) if end_period is not None else last
        first = add_months(last, 1 - context_months)
        by_key = await self._values(work, ids, sex, first, last)
        periods = tuple(add_months(first, offset) for offset in range(context_months))
        values: dict[int, list[float | None]] = {}
        provisional: dict[int, list[bool | None]] = {}
        estimated: dict[int, list[bool | None]] = {}
        for county_id in ids:
            points = [by_key.get((county_id, period)) for period in periods]
            values[county_id] = [None if p is None else p.value for p in points]
            provisional[county_id] = [None if p is None else p.is_provisional for p in points]
            estimated[county_id] = [None if p is None else p.is_estimated for p in points]
        return CountySeries(periods=periods, values=values, provisional=provisional, estimated=estimated,
                            sources=found, latest_source_period=latest)

    def after(self, period: date, steps: int) -> date:
        return add_months(period, steps)

    async def _last_period(self, work: UnitOfWork, ids: Sequence[int], sex: DzsSex) -> date | None:
        """The latest month with a value for every county."""
        return await latest_common(work, ids, self._indicator, sex)

    async def _values(self, work: UnitOfWork, ids: Sequence[int], sex: DzsSex, first: date, last: date,
                      ) -> MonthValues:
        """The known values from first to last; a month without one has no entry."""
        return await stored_values(work, ids, self._indicator, sex, first, last)


class DzsPersonsSeriesLoader(DzsSeriesLoader):
    """DzsPersonsSeriesLoader reads DZS unemployed or employed persons, estimating months DZS gives no count for.

    DZS publishes exact counts only for the months of its latest release,
    but the rate and active population back to 2020, and defines the rate as
    unemployed per active population. So unemployed is estimated as rate x
    active population / 100 and employed as active population minus that.
    An exact count always wins. The rate has one decimal, so an estimate can
    be off by up to 0.05% of the active population.
    """

    def __init__(self, indicator: DzsIndicator, notes: tuple[str, ...]) -> None:
        if indicator not in ("unemployed", "employed"):
            raise ValueError(f"Only unemployed and employed can be estimated, not {indicator}.")
        super().__init__(indicator, "persons", 0, None, (*notes, NOTE_ESTIMATED))

    async def _last_period(self, work: UnitOfWork, ids: Sequence[int], sex: DzsSex) -> date | None:
        exact = await latest_common(work, ids, self._indicator, sex)
        rate = await latest_common(work, ids, "unemployment_rate", sex)
        active = await self._active_last(work, ids, sex)
        estimated = None if rate is None or active is None else min(rate, active)
        known = [period for period in (exact, estimated) if period is not None]
        return max(known) if known else None

    async def _values(self, work: UnitOfWork, ids: Sequence[int], sex: DzsSex, first: date, last: date,
                      ) -> MonthValues:
        rates = await stored_values(work, ids, "unemployment_rate", sex, first, last)
        active = await self._active(work, ids, sex, first, last)
        values: MonthValues = {}
        for key in rates.keys() & active.keys():
            unemployed = rates[key].value * active[key].value / 100
            values[key] = MonthValue(
                value=unemployed if self._indicator == "unemployed" else active[key].value - unemployed,
                is_provisional=rates[key].is_provisional or active[key].is_provisional, is_estimated=True)
        return values | await stored_values(work, ids, self._indicator, sex, first, last)

    @staticmethod
    async def _active_last(work: UnitOfWork, ids: Sequence[int], sex: DzsSex) -> date | None:
        if sex != "men":
            return await latest_common(work, ids, "active_population", sex)
        periods = [await latest_common(work, ids, "active_population", part) for part in ("total", "women")]
        return None if None in periods else min(periods)

    @staticmethod
    async def _active(work: UnitOfWork, ids: Sequence[int], sex: DzsSex, first: date, last: date) -> MonthValues:
        """Active population by county and month; DZS has none for men, so men are total minus women."""
        if sex != "men":
            return await stored_values(work, ids, "active_population", sex, first, last)
        total = await stored_values(work, ids, "active_population", "total", first, last)
        women = await stored_values(work, ids, "active_population", "women", first, last)
        return {key: MonthValue(value=total[key].value - women[key].value,
                                is_provisional=total[key].is_provisional or women[key].is_provisional)
                for key in total.keys() & women.keys()}


async def latest_common(work: UnitOfWork, ids: Sequence[int], indicator: DzsIndicator, sex: DzsSex) -> date | None:
    return (await work.dzs_indicator_values.latest_common_periods(ids, (indicator,), sex)).get(indicator)


async def stored_values(work: UnitOfWork, ids: Sequence[int], indicator: DzsIndicator, sex: DzsSex, first: date,
                        last: date) -> MonthValues:
    stored = await work.dzs_indicator_values.list_series(ids, indicator, sex, first, last)
    return {(value.county_id, value.period): MonthValue(value=float(value.value), is_provisional=value.is_provisional)
            for value in stored if value.value is not None}


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
