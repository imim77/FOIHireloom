import math
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic import ValidationError

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.dzs import DzsImportProvenanceDTO, DzsStoredValueDTO
from FOIHireloom.dto.forecast import QuantileForecastDTO
from FOIHireloom.dto.forecast_accuracy import ForecastAccuracyPointDTO, ForecastAccuracyRequestDTO
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError
from FOIHireloom.factories.forecast_accuracy import ForecastAccuracyServiceFactory
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface
from FOIHireloom.services.concrete.county_indicators import add_months
from FOIHireloom.services.concrete.forecast_accuracy_calculation import accuracy_metrics, rate_predictions

COUNTY = CountyDTO(id=5, code="varazdinska", name="Varaždinska županija", iso_code="HR-05")
OTHER = CountyDTO(id=20, code="medimurska", name="Međimurska županija", iso_code="HR-20")
LAST = date(2026, 9, 1)
PROVENANCE = DzsImportProvenanceDTO(import_id=1, finished_at=datetime(2026, 11, 2, tzinfo=UTC), files=())


def stored(count=48, county=COUNTY):
    return [DzsStoredValueDTO(
        county_id=county.id, indicator="unemployment_rate", sex="total", period=add_months(LAST, index - count + 1),
        value=Decimal(str(2 + index / 10)), missing_reason=None,
        is_provisional=index >= count - 9, source="workbook_9_4_14",
    ) for index in range(count)]


class SnapshotWork:
    def __init__(self, rows=None, provenance=PROVENANCE, latest=LAST):
        self.active = False
        self.counties = SimpleNamespace(list_all=AsyncMock(return_value=[COUNTY, OTHER]))
        self.dzs_imports = SimpleNamespace(get_latest_succeeded=AsyncMock(return_value=provenance))
        self.dzs_indicator_values = SimpleNamespace(
            latest_common_periods=AsyncMock(return_value={} if latest is None else {"unemployment_rate": latest}),
            list_series=AsyncMock(return_value=stored() if rows is None else rows))
        self.transaction_time = AsyncMock(return_value=datetime(2026, 11, 5, tzinfo=UTC))

    async def __aenter__(self):
        self.active = True
        return self

    async def __aexit__(self, *exc):
        self.active = False


class RecordingForecaster(TimeSeriesForecasterInterface):
    def __init__(self, work):
        self.work = work
        self.calls = []
        self.results = None

    @property
    def model_name(self):
        return "test/constant-model"

    async def forecast(self, histories, horizon):
        if self.work.active:
            raise AssertionError("The database transaction must close before inference")
        self.calls.append(([list(values) for values in histories], horizon))
        return self.results if self.results is not None else [
            QuantileForecastDTO(low=(4.0,) * horizon, median=(5.0,) * horizon, high=(6.0,) * horizon)
            for _ in histories
        ]


def service(work, forecaster=None):
    model = forecaster or RecordingForecaster(work)
    return ForecastAccuracyServiceFactory(Settings(_env_file=None)).create(lambda: work, model), model


def point(actual, median, baseline, low=2.0, high=4.0, provisional=False):
    return ForecastAccuracyPointDTO(period=LAST, step=1, actual=actual, median=median,
                                    low=low, high=high, seasonal_naive=baseline, is_provisional=provisional)


class AccuracyCalculationTests(unittest.TestCase):
    def test_scores_hand_calculated_errors_and_inclusive_interval_edges(self):
        metrics = accuracy_metrics([point(2, 3, 4), point(4, 4, 2, provisional=True)])
        self.assertEqual((metrics.observations, metrics.provisional_observations), (2, 1))
        self.assertEqual((metrics.mae_pp, metrics.seasonal_naive_mae_pp, metrics.mae_skill), (0.5, 2, 0.75))
        self.assertEqual((metrics.interval_coverage, metrics.mean_interval_width_pp), (1, 2))
        self.assertEqual(accuracy_metrics([point(5, 4, 3)]).interval_coverage, 0)

    def test_empty_samples_and_perfect_baselines_do_not_create_fake_skill(self):
        empty = accuracy_metrics([])
        self.assertEqual(empty.observations, 0)
        self.assertIsNone(empty.mae_pp)
        self.assertIsNone(empty.interval_coverage)
        self.assertIsNone(accuracy_metrics([point(2, 3, 2)]).mae_skill)
        self.assertEqual(accuracy_metrics([point(2, 2, 2)]).mae_pp, 0)

    def test_applies_production_rounding_and_bounds_after_checking_quantiles(self):
        prediction = QuantileForecastDTO(low=(-1, 99.94), median=(0.06, 100), high=(2.04, 101))
        self.assertEqual(rate_predictions(prediction, 2), [(0, 0.1, 2), (99.9, 100, 100)])
        for bad in (QuantileForecastDTO(low=(0,), median=(1,), high=(2,)),
                    QuantileForecastDTO(low=(3, 3), median=(2, 2), high=(4, 4)),
                    QuantileForecastDTO(low=(0, 0), median=(math.nan, 1), high=(2, 2)),
                    QuantileForecastDTO(low=(0, 0), median=(1, 1), high=(math.inf, 2))):
            with self.subTest(bad=bad), self.assertRaises(ForecastUnavailableError):
                rate_predictions(bad, 2)


class ForecastAccuracyServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_origin_withholds_its_future_and_baseline_uses_only_prior_years(self):
        rows = stored()
        work = SnapshotWork(rows)
        evaluator, model = service(work)
        report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,)))
        windows = report.counties[0].windows
        self.assertEqual([window.cutoff for window in windows], [date(2026, month, 1) for month in (1, 2, 3)])
        for window, (inputs, horizon) in zip(windows, model.calls, strict=True):
            self.assertEqual(horizon, 6)
            self.assertEqual(inputs, [[float(row.value) for row in rows if row.period <= window.cutoff]])
            self.assertEqual(window.training_known_values, len(inputs[0]))
            for p in window.points:
                self.assertGreater(p.period, window.cutoff)
                baseline_month = add_months(p.period, -12)
                self.assertLessEqual(baseline_month, window.cutoff)
                self.assertEqual(p.seasonal_naive, float(next(row.value for row in rows if row.period == baseline_month)))
        self.assertEqual((report.status, report.evaluated_windows, report.skipped_windows), ("evaluated", 3, 0))
        self.assertEqual(report.metrics.observations, 18)
        self.assertEqual([step.metrics.observations for step in report.by_horizon], [3] * 6)
        self.assertEqual(report.dzs, PROVENANCE)
        self.assertEqual(len(report.dataset_sha256), 64)
        self.assertIn("revised", report.notes[0])
        self.assertEqual(report.evaluation_basis, "latest_revised_data")

    async def test_changing_held_out_values_changes_scores_but_not_model_inputs(self):
        original = stored()
        changed = [row.model_copy(update={"value": Decimal("50")}) if row.period > date(2026, 3, 1) else row
                   for row in original]
        first, first_model = service(SnapshotWork(original))
        second, second_model = service(SnapshotWork(changed))
        request = ForecastAccuracyRequestDTO(counties=(COUNTY.code,), windows=1)
        before = await first.evaluate(request)
        after = await second.evaluate(request)
        self.assertEqual(first_model.calls, second_model.calls)
        self.assertNotEqual(before.metrics.mae_pp, after.metrics.mae_pp)
        self.assertNotEqual(before.dataset_sha256, after.dataset_sha256)

    async def test_early_origins_keep_the_full_live_context_and_no_later_rows_are_loaded_for_explicit_end(self):
        rows = stored(156)
        work = SnapshotWork(rows)
        evaluator, model = service(work)
        report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,)))
        self.assertEqual([len(inputs[0]) for inputs, _ in model.calls], [120, 120, 120])
        for window, (inputs, _) in zip(report.counties[0].windows, model.calls, strict=True):
            first = add_months(window.cutoff, -119)
            self.assertEqual(inputs[0], [float(row.value) for row in rows if first <= row.period <= window.cutoff])
        end = date(2024, 9, 1)
        await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), end_period=end))
        self.assertEqual(work.dzs_indicator_values.list_series.call_args.args[-1], end)

    async def test_explicit_end_month_and_sex_are_used_and_future_end_is_rejected(self):
        work = SnapshotWork()
        evaluator, _ = service(work)
        report = await evaluator.evaluate(ForecastAccuracyRequestDTO(
            counties=(COUNTY.code,), sex="women", end_period=date(2025, 9, 1), horizon=12, windows=1))
        window = report.counties[0].windows[0]
        self.assertEqual(window.cutoff, date(2024, 9, 1))
        self.assertEqual(window.points[-1].period, date(2025, 9, 1))
        self.assertEqual(report.latest_source_period, LAST)
        self.assertEqual(report.end_period, date(2025, 9, 1))
        self.assertEqual(work.dzs_indicator_values.list_series.call_args.args[2], "women")
        with self.assertRaises(InvalidIndicatorRequestError):
            await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), end_period=date(2027, 1, 1)))

    async def test_missing_data_skips_whole_paired_windows_without_calling_the_model(self):
        for reason, missing in (("missing_training_endpoint", date(2026, 3, 1)),
                                ("missing_actuals", date(2026, 5, 1)),
                                ("missing_seasonal_baseline", date(2025, 5, 1))):
            rows = [row.model_copy(update={"value": None}) if row.period == missing else row for row in stored()]
            evaluator, model = service(SnapshotWork(rows))
            report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), windows=1))
            with self.subTest(reason=reason):
                self.assertEqual(report.counties[0].windows[0].unavailable_reason, reason)
                self.assertEqual(report.skipped_windows, 1)
                self.assertEqual(report.status, "unavailable")
                self.assertIsNone(report.metrics.mae_pp)
                self.assertEqual(model.calls, [])

    async def test_interior_training_gaps_are_nan_and_zero_rates_remain_known(self):
        rows = stored()
        rows[1] = rows[1].model_copy(update={"value": None})
        rows[2] = rows[2].model_copy(update={"value": Decimal(0)})
        evaluator, model = service(SnapshotWork(rows))
        report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), windows=1))
        self.assertTrue(math.isnan(model.calls[0][0][0][1]))
        self.assertEqual(model.calls[0][0][0][2], 0)
        self.assertEqual(report.status, "evaluated")

    async def test_short_or_absent_series_never_load_the_model_or_report_perfect_accuracy(self):
        for work in (SnapshotWork(stored(29)), SnapshotWork(provenance=None), SnapshotWork(latest=None)):
            evaluator, model = service(work)
            report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), windows=1))
            self.assertEqual(report.status, "unavailable")
            self.assertEqual(report.metrics.observations, 0)
            self.assertIsNone(report.metrics.mae_pp)
            self.assertEqual(model.calls, [])

    async def test_county_order_and_batching_are_preserved_and_aggregates_are_pair_weighted(self):
        evaluator, model = service(SnapshotWork(stored() + stored(county=OTHER)))
        report = await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(OTHER.code, COUNTY.name), windows=2))
        self.assertEqual([county.code for county in report.counties], [OTHER.code, COUNTY.code])
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(len(model.calls[0][0]), 2)
        self.assertEqual(report.metrics.observations, 24)
        self.assertEqual(report.metrics.mae_pp, accuracy_metrics(
            [p for county in report.counties for window in county.windows for p in window.points]).mae_pp)

    async def test_wrong_series_count_and_invalid_quantiles_abort_instead_of_scoring(self):
        for predictions in ([], [QuantileForecastDTO(low=(0,), median=(1,), high=(2,))]):
            work = SnapshotWork()
            model = RecordingForecaster(work)
            model.results = predictions
            evaluator, _ = service(work, model)
            with self.assertRaises(ForecastUnavailableError):
                await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,), windows=1))

    async def test_duplicate_and_unknown_counties_are_rejected(self):
        evaluator, model = service(SnapshotWork())
        for counties in ((COUNTY.code, COUNTY.name), ("unknown",)):
            with self.assertRaises(InvalidIndicatorRequestError):
                await evaluator.evaluate(ForecastAccuracyRequestDTO(counties=counties))
        self.assertEqual(model.calls, [])

    def test_request_limits_prevent_unbounded_work_and_invalid_baseline_horizons(self):
        for extra in ({"horizon": 0}, {"horizon": 13}, {"windows": 0}, {"windows": 13},
                      {"end_period": date(2026, 9, 2)}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                ForecastAccuracyRequestDTO(counties=(COUNTY.code,), **extra)
