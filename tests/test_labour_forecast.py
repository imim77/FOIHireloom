import asyncio
import importlib.util
import math
import unittest
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from FOIHireloom.api.forecast_tools import LABOUR_FORECAST_SERVICE, ForecastTools
from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.dzs import DzsImportProvenanceDTO, DzsStoredValueDTO
from FOIHireloom.dto.forecast import (
    CountyForecastDTO,
    CountyForecastRequestDTO,
    QuantileForecastDTO,
    WeeklyJobAdsRowDTO,
)
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError
from FOIHireloom.factories.labour_forecast import LabourMarketForecastServiceFactory
from FOIHireloom.integrations.concrete.chronos import ChronosForecaster
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.concrete.county_indicators import add_months
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface

VARAZDINSKA = CountyDTO(id=5, code="varazdinska", name="Varaždinska županija", iso_code="HR-05")
MEDIMURSKA = CountyDTO(id=20, code="medimurska", name="Međimurska županija", iso_code="HR-20")
LAST_MONTH = date(2026, 8, 1)
PROVENANCE = DzsImportProvenanceDTO(import_id=1, finished_at=datetime(2026, 10, 1, tzinfo=UTC), files=())


class FakeForecaster(TimeSeriesForecasterInterface):
    """Returns low, median and high as fixed offsets from the last known value, and records its input."""

    def __init__(self, low: float = -1.0, high: float = 1.0) -> None:
        self.calls: list[tuple[list[list[float]], int]] = []
        self._low = low
        self._high = high

    @property
    def model_name(self) -> str:
        return "amazon/chronos-2"

    async def forecast(self, histories: Sequence[Sequence[float]], horizon: int) -> list[QuantileForecastDTO]:
        self.calls.append(([list(history) for history in histories], horizon))
        results = []
        for history in histories:
            last = next(value for value in reversed(history) if not math.isnan(value))
            results.append(QuantileForecastDTO(
                low=tuple(last + self._low for _ in range(horizon)),
                median=tuple(last + 0.04 * (step + 1) for step in range(horizon)),
                high=tuple(last + self._high for _ in range(horizon))))
        return results


def rate(county: CountyDTO, period: date, value: str | None, provisional: bool = False) -> DzsStoredValueDTO:
    return DzsStoredValueDTO(county_id=county.id, indicator="unemployment_rate", period=period, sex="total",
                             value=None if value is None else Decimal(value),
                             missing_reason="not_available" if value is None else None,
                             is_provisional=provisional, source="workbook_9_4_14")


def months_back(count: int) -> list[date]:
    return [add_months(LAST_MONTH, offset - count + 1) for offset in range(count)]


class FakeWork:
    def __init__(self, *, provenance=PROVENANCE, latest=None, series=(), tracking=None, weekly=(),
                 now=datetime(2026, 11, 4, 12, tzinfo=UTC)) -> None:
        self.counties = SimpleNamespace(list_all=AsyncMock(return_value=[VARAZDINSKA, MEDIMURSKA]))
        self.dzs_imports = SimpleNamespace(get_latest_succeeded=AsyncMock(return_value=provenance))
        self.dzs_indicator_values = SimpleNamespace(
            latest_common_periods=AsyncMock(return_value={} if latest is None else {"unemployment_rate": latest}),
            list_series=AsyncMock(return_value=list(series)))
        self.jobs = SimpleNamespace(tracking_started_at=AsyncMock(return_value=tracking),
                                    weekly_published_counts=AsyncMock(return_value=list(weekly)))
        self.transaction_time = AsyncMock(return_value=now)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None


def service(work: FakeWork, forecaster: FakeForecaster) -> LabourMarketForecastServiceInterface:
    return LabourMarketForecastServiceFactory(Settings(_env_file=None)).create(lambda: work, forecaster)


class DzsForecastTests(unittest.IsolatedAsyncioTestCase):
    async def test_forecasts_counties_with_enough_history_and_explains_the_rest(self) -> None:
        series = [rate(VARAZDINSKA, month, "5.0", provisional=month.year == 2026) for month in months_back(36)]
        series[-3] = rate(VARAZDINSKA, months_back(36)[-3], None)  # A gap stays a gap.
        series += [rate(MEDIMURSKA, month, "3.0") for month in months_back(10)]
        work = FakeWork(latest=LAST_MONTH, series=series)
        forecaster = FakeForecaster()

        result = await service(work, forecaster).forecast(CountyForecastRequestDTO(
            counties=("Varaždinska županija", "medimurska"), target="unemployment_rate", horizon=3, sex="women"))

        (histories, horizon), = forecaster.calls
        self.assertEqual((len(histories), len(histories[0]), horizon), (1, 36, 3))  # Months before 2020 trimmed.
        self.assertTrue(math.isnan(histories[0][-3]))
        work.dzs_indicator_values.list_series.assert_awaited_once_with(
            (5, 20), "unemployment_rate", "women", date(2016, 9, 1), LAST_MONTH)
        varazdinska, medimurska = result.counties
        self.assertEqual([point.period for point in varazdinska.forecast],
                         [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)])
        self.assertEqual([(p.low, p.median, p.high) for p in varazdinska.forecast],
                         [(4.0, 5.0, 6.0), (4.0, 5.1, 6.0), (4.0, 5.1, 6.0)])
        self.assertEqual((varazdinska.change_to_horizon, varazdinska.last_observed.value), (0.1, 5.0))
        self.assertEqual(len(varazdinska.history), 24)
        self.assertTrue(varazdinska.history[-1].is_provisional)
        self.assertIsNone(varazdinska.history[-3].value)
        self.assertEqual((medimurska.forecast, medimurska.unavailable_reason), ((), "not_enough_history"))
        self.assertEqual(len(medimurska.history), 24)
        self.assertEqual((result.frequency, result.unit, result.sex, result.horizon, result.last_observed_period),
                         ("month", "percent", "women", 3, LAST_MONTH))
        self.assertEqual(result.sources[-1].url, "https://huggingface.co/amazon/chronos-2")
        self.assertIn("80% interval", " ".join(result.notes))

    async def test_keeps_forecasts_within_the_units_range(self) -> None:
        series = [rate(VARAZDINSKA, month, "99.5") for month in months_back(30)]
        forecaster = FakeForecaster(low=-150.0, high=3.0)
        result = await service(FakeWork(latest=LAST_MONTH, series=series), forecaster).forecast(
            CountyForecastRequestDTO(counties=("varazdinska",), target="unemployment_rate", horizon=1))
        point = result.counties[0].forecast[0]
        self.assertEqual((point.low, point.high), (0.0, 100.0))

    async def test_without_dzs_data_no_county_is_forecast(self) -> None:
        for work, reason in ((FakeWork(provenance=None), "no_dzs_data"), (FakeWork(latest=None), "no_common_period")):
            forecaster = FakeForecaster()
            result = await service(work, forecaster).forecast(
                CountyForecastRequestDTO(counties=("varazdinska",), target="unemployed"))
            self.assertEqual((result.unavailable_reason, result.counties[0].unavailable_reason), (reason, reason))
            self.assertEqual((result.counties[0].forecast, result.last_observed_period, result.horizon), ((), None, 12))
            self.assertEqual(forecaster.calls, [([], 12)])

    async def test_rejects_horizons_and_county_lists_out_of_range(self) -> None:
        cases = (
            CountyForecastRequestDTO(counties=("varazdinska",), target="employed", horizon=25),
            CountyForecastRequestDTO(counties=("varazdinska",), target="job_ads", horizon=27),
            CountyForecastRequestDTO(counties=("varazdinska",) * 7, target="employed"),
            CountyForecastRequestDTO(counties=("varazdinska", "varazdinska"), target="employed"),
            CountyForecastRequestDTO(counties=("atlantida",), target="employed"),
        )
        for request in cases:
            with self.subTest(request=request), self.assertRaises(InvalidIndicatorRequestError):
                await service(FakeWork(latest=LAST_MONTH), FakeForecaster()).forecast(request)


class FakeDzsValues:
    """Answers the DZS repository's queries from a list of stored values, as the database would."""

    def __init__(self, values: list[DzsStoredValueDTO]) -> None:
        self._values = values

    async def list_series(self, county_ids, indicator, sex, first, last):
        return [v for v in self._values if v.county_id in county_ids and v.indicator == indicator and v.sex == sex
                and first <= v.period <= last]

    async def latest_common_periods(self, county_ids, indicators, sex):
        latest = {}
        for indicator in indicators:
            periods = {v.period for v in self._values if v.indicator == indicator and v.sex == sex}
            common = [p for p in periods if all(any(v.county_id == c and v.period == p and v.value is not None
                                                    and v.indicator == indicator and v.sex == sex
                                                    for v in self._values) for c in county_ids)]
            if common:
                latest[indicator] = max(common)
        return latest


def stored(indicator: str, sex: str, period: date, value: str, provisional: bool = False) -> DzsStoredValueDTO:
    return DzsStoredValueDTO(county_id=VARAZDINSKA.id, indicator=indicator, period=period, sex=sex,
                             value=Decimal(value), missing_reason=None, is_provisional=provisional,
                             source="t1" if indicator in ("unemployed", "employed") else "workbook_9_4_14")


class PersonsForecastTests(unittest.IsolatedAsyncioTestCase):
    def work(self, values: list[DzsStoredValueDTO]) -> FakeWork:
        work = FakeWork()
        work.dzs_indicator_values = FakeDzsValues(values)
        return work

    async def test_estimates_months_without_an_exact_count(self) -> None:
        months = months_back(30)
        values = [stored("unemployment_rate", "total", m, "5.0") for m in months]
        values += [stored("active_population", "total", m, "80000", provisional=m == LAST_MONTH) for m in months]
        values += [stored("unemployed", "total", LAST_MONTH, "3990"), stored("employed", "total", LAST_MONTH, "76010")]
        for target, estimate, exact in (("unemployed", 4000.0, 3990.0), ("employed", 76000.0, 76010.0)):
            forecaster = FakeForecaster()
            result = await service(self.work(values), forecaster).forecast(
                CountyForecastRequestDTO(counties=("varazdinska",), target=target, horizon=1))
            (histories, _), = forecaster.calls
            self.assertEqual(histories[0][-2:], [estimate, exact])  # The exact count wins.
            county = result.counties[0]
            self.assertEqual([(p.value, p.is_estimated) for p in county.history[-2:]],
                             [(estimate, True), (exact, False)])
            self.assertEqual(county.unavailable_reason, None)
            self.assertIn("estimated", " ".join(result.notes))

    async def test_men_use_total_minus_women_active_population(self) -> None:
        months = months_back(24)
        values = [stored("unemployment_rate", "men", m, "4.0") for m in months]
        values += [stored("active_population", "total", m, "80000") for m in months]
        values += [stored("active_population", "women", m, "30000", provisional=True) for m in months]
        forecaster = FakeForecaster()
        result = await service(self.work(values), forecaster).forecast(
            CountyForecastRequestDTO(counties=("varazdinska",), target="unemployed", horizon=1, sex="men"))
        self.assertEqual(forecaster.calls[0][0][0], [2000.0] * 24)
        self.assertTrue(result.counties[0].history[-1].is_provisional)
        self.assertEqual(result.last_observed_period, LAST_MONTH)


class JobAdsForecastTests(unittest.IsolatedAsyncioTestCase):
    async def test_counts_full_weeks_since_tracking_began(self) -> None:
        # Tracking began on Wednesday 2026-08-26; today is Wednesday 2026-11-04.
        weekly = [WeeklyJobAdsRowDTO(county_id=5, week=date(2026, 9, 7), jobs=12),
                  WeeklyJobAdsRowDTO(county_id=5, week=date(2026, 10, 26), jobs=30)]
        work = FakeWork(tracking=datetime(2026, 8, 26, 9, tzinfo=UTC), weekly=weekly)
        forecaster = FakeForecaster()

        result = await service(work, forecaster).forecast(
            CountyForecastRequestDTO(counties=("varazdinska",), target="job_ads", horizon=2, sex="women"))

        work.jobs.weekly_published_counts.assert_awaited_once_with((5,), date(2026, 8, 31), date(2026, 10, 26))
        (histories, _), = forecaster.calls
        self.assertEqual(histories, [[0.0, 12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 30.0]])
        county = result.counties[0]
        self.assertEqual([point.period for point in county.forecast], [date(2026, 11, 2), date(2026, 11, 9)])
        self.assertEqual(county.forecast[0].median, 30.0)
        self.assertEqual(county.last_observed.period, date(2026, 10, 26))
        self.assertEqual((result.frequency, result.unit, result.sex), ("week", "ads", None))
        self.assertEqual(result.sources[0].name, "HZZ")

    async def test_short_or_missing_hzz_history_is_explained(self) -> None:
        recent = FakeWork(tracking=datetime(2026, 10, 1, tzinfo=UTC))
        result = await service(recent, FakeForecaster()).forecast(
            CountyForecastRequestDTO(counties=("varazdinska",), target="job_ads"))
        self.assertEqual(result.counties[0].unavailable_reason, "not_enough_history")
        self.assertEqual(len(result.counties[0].history), 4)
        result = await service(FakeWork(), FakeForecaster()).forecast(
            CountyForecastRequestDTO(counties=("varazdinska",), target="job_ads"))
        self.assertEqual((result.unavailable_reason, result.counties[0].history), ("no_hzz_data", ()))


class FakePipeline:
    def __init__(self, chronos2: bool) -> None:
        self.chronos2 = chronos2
        self.inputs = None

    def predict_quantiles(self, inputs, prediction_length, quantile_levels):
        import torch

        self.inputs = inputs
        steps = torch.arange(prediction_length, dtype=torch.float32)
        one = torch.stack([steps, steps + 10, steps + 20], dim=-1)  # (horizon, quantiles)
        if self.chronos2:
            return [one.unsqueeze(0) for _ in inputs], None
        return torch.stack([one for _ in inputs]), None


@unittest.skipUnless(importlib.util.find_spec("torch"), "needs the forecast extra")
class ChronosForecasterTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_quantiles_of_every_chronos_family(self) -> None:
        for chronos2 in (True, False):
            pipeline = FakePipeline(chronos2)
            forecaster = ChronosForecaster("amazon/chronos-2", load=lambda pipeline=pipeline: pipeline)
            forecasts = await forecaster.forecast([[1.0, math.nan, 3.0], [4.0, 5.0]], 2)
            self.assertEqual([len(series) for series in pipeline.inputs], [3, 2])
            self.assertEqual(forecasts, [QuantileForecastDTO(low=(0.0, 1.0), median=(10.0, 11.0),
                                                             high=(20.0, 21.0))] * 2)

    async def test_loads_the_model_once_for_concurrent_forecasts(self) -> None:
        loads = []

        def load():
            loads.append(1)
            return FakePipeline(True)

        forecaster = ChronosForecaster("amazon/chronos-2", load=load)
        await asyncio.gather(*(forecaster.forecast([[1.0, 2.0]], 1) for _ in range(3)))
        self.assertEqual(len(loads), 1)
        self.assertEqual(await forecaster.forecast([], 1), [])

    async def test_model_failures_become_forecast_unavailable(self) -> None:
        def missing():
            raise ForecastUnavailableError("Forecasting needs Amazon Chronos.")

        with self.assertRaisesRegex(ForecastUnavailableError, "needs Amazon Chronos"):
            await ChronosForecaster("amazon/chronos-2", load=missing).forecast([[1.0]], 1)
        broken = SimpleNamespace(predict_quantiles=lambda *args, **kwargs: 1 / 0)
        with self.assertRaisesRegex(ForecastUnavailableError, "failed"), self.assertLogs(level="ERROR"):
            await ChronosForecaster("amazon/chronos-2", load=lambda: broken).forecast([[1.0]], 1)


class FakeForecastService(LabourMarketForecastServiceInterface):
    def __init__(self) -> None:
        self.requests: list[CountyForecastRequestDTO] = []
        self.error: Exception | None = None

    async def forecast(self, request: CountyForecastRequestDTO) -> CountyForecastDTO:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return CountyForecastDTO(target=request.target, frequency="month", unit="percent", sex=request.sex,
                                 horizon=request.horizon or 12, model="amazon/chronos-2", last_observed_period=None,
                                 counties=(), unavailable_reason="no_dzs_data", sources=(), notes=())


class ForecastToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = FakeForecastService()

        @asynccontextmanager
        async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
            yield {LABOUR_FORECAST_SERVICE: self.service}

        self.server = FastMCP("test", lifespan=lifespan, mask_error_details=True)
        ForecastTools().register(self.server)

    async def test_passes_the_request_and_returns_structured_data(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("forecast_labour_market", {
                "counties": ["varazdinska"], "target": "unemployment_rate", "horizon": 6})
        self.assertEqual(self.service.requests, [CountyForecastRequestDTO(
            counties=("varazdinska",), target="unemployment_rate", horizon=6)])
        self.assertEqual(result.structured_content["unavailable_reason"], "no_dzs_data")

    async def test_turns_actionable_errors_into_tool_errors(self) -> None:
        for error, message in ((ForecastUnavailableError("Install the forecast extra."), "forecast extra"),
                               (InvalidIndicatorRequestError("Unknown county: x."), "Unknown county")):
            self.service.error = error
            async with Client(self.server) as client:
                with self.subTest(error=error), self.assertRaisesRegex(ToolError, message):
                    await client.call_tool("forecast_labour_market", {"counties": ["x"], "target": "employed"})


if __name__ == "__main__":
    unittest.main()
