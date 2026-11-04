import unittest
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import CountyComparisonRequestDTO, DzsReferencePeriodDTO
from FOIHireloom.dto.dzs import DzsStoredValueDTO
from FOIHireloom.dto.job_market import CountyJobCountsRowDTO, JobCountFiltersDTO
from FOIHireloom.dto.job_search import CountyFeedCheckDTO, RegionFreshnessDTO
from FOIHireloom.exceptions import InvalidIndicatorRequestError
from FOIHireloom.factories.county_indicators import CountyIndicatorServiceFactory
from FOIHireloom.services.concrete.county_indicator_calculation import COMPARED_INDICATORS, CountyIndicatorCalculator

PERIOD = date(2026, 9, 1)
NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
COUNTY = CountyDTO(id=1, code="istarska", name="Istarska županija", iso_code="HR-18")
OTHER = CountyDTO(id=2, code="varazdinska", name="Varaždinska županija", iso_code="HR-05")
REGION = RegionFreshnessDTO(code=COUNTY.code, name=COUNTY.name, data_status="fresh", last_success_at=NOW)


def counts(**changes) -> CountyJobCountsRowDTO:
    return CountyJobCountsRowDTO(**(dict(county_id=1, jobs=5, with_workers_needed=3, workers_needed=6,
                                        with_contract=4, permanent=1, closing_soon=2) | changes))


def value(indicator="unemployment_rate", rate="2.3", period=PERIOD) -> DzsStoredValueDTO:
    return DzsStoredValueDTO(county_id=1, indicator=indicator, period=period, sex="total", value=Decimal(rate),
                             missing_reason=None, is_provisional=True, source="t1")


class CountyIndicatorCalculationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = CountyIndicatorCalculator()
        self.periods = {indicator: DzsReferencePeriodDTO(indicator=indicator, period=PERIOD, requested=False,
                                                        unavailable_reason=None) for indicator in COMPARED_INDICATORS}
        self.values = {(1, indicator): value(indicator, number)
                       for indicator, number in [("unemployed", "12"), ("active_population", "1000"),
                                                  ("unemployment_rate", "2.3")]}

    def compare(self, everything, region=REGION, periods=None):
        return self.calculator.compare(COUNTY, region, counts(jobs=1), everything,
                                       self.periods if periods is None else periods, self.values)

    def test_ratios_use_all_active_ads_and_preserve_provisional_flags(self) -> None:
        compared = self.compare(counts())
        self.assertEqual((compared.filtered_jobs.jobs, compared.all_active_jobs.jobs), (1, 5))
        self.assertEqual(compared.unemployed_per_worker.value, Decimal("2.0"))
        self.assertEqual(compared.jobs_per_1000_active.value, Decimal("5.0"))
        self.assertEqual(compared.all_active_jobs.workers_needed_coverage.percent, Decimal("60.0"))
        self.assertEqual(compared.all_active_jobs.permanent_share.percent, Decimal("25.0"))
        self.assertTrue(compared.unemployed_per_worker.is_provisional)

    def test_unknown_workers_zero_workers_and_unloaded_counties_have_distinct_reasons(self) -> None:
        unknown = self.compare(counts(with_workers_needed=0, workers_needed=0))
        empty = self.compare(None)
        unloaded = self.compare(None, region=None)
        self.assertEqual(unknown.unemployed_per_worker.unavailable_reason, "no_known_workers")
        self.assertIsNone(unknown.unemployed_per_worker.denominator)
        self.assertEqual(empty.unemployed_per_worker.unavailable_reason, "zero_denominator")
        self.assertEqual(empty.unemployed_per_worker.denominator, 0)
        self.assertEqual(empty.jobs_per_1000_active.value, Decimal("0.0"))
        self.assertEqual(unloaded.unemployed_per_worker.unavailable_reason, "no_hzz_data")
        self.assertIsNone(unloaded.jobs_per_1000_active.value)

    def test_missing_dzs_period_takes_precedence_over_missing_hzz(self) -> None:
        periods = {indicator: reference.model_copy(update={"period": None, "unavailable_reason": "no_common_period"})
                   for indicator, reference in self.periods.items()}
        compared = self.compare(None, region=None, periods=periods)
        self.assertEqual(compared.unemployed_per_worker.unavailable_reason, "no_common_period")
        self.assertIsNone(compared.unemployed_per_worker.value)
        self.assertIsNone(compared.unemployed.period)

    def test_history_keeps_gaps_and_treats_zero_as_a_known_rate(self) -> None:
        before = date(2025, 9, 1)
        rates = {(1, PERIOD): value(rate="0.0"), (1, before): value(rate="1.3", period=before)}
        history = self.calculator.history(COUNTY, rates, [date(2026, 8, 1), PERIOD], before)
        self.assertIsNone(history.series[0].rate)
        self.assertEqual(history.series[0].unavailable_reason, "dzs_value_missing")
        self.assertEqual(history.latest.rate, Decimal("0.0"))
        self.assertEqual(history.change_pp, Decimal("-1.3"))
        self.assertIsNone(history.change_unavailable_reason)
        del rates[(1, before)]
        missing = self.calculator.history(COUNTY, rates, [PERIOD], before)
        self.assertIsNone(missing.change_pp)
        self.assertEqual(missing.change_unavailable_reason, "dzs_value_missing")


class CountyIndicatorServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.work = SimpleNamespace(
            transaction_time=AsyncMock(return_value=NOW),
            counties=SimpleNamespace(list_all=AsyncMock(return_value=[COUNTY, OTHER]),
                list_feed_checks=AsyncMock(return_value=[CountyFeedCheckDTO(
                    code=county.code, name=county.name, feed_id=county.id, last_success_at=NOW,
                ) for county in (COUNTY, OTHER)])),
            jobs=SimpleNamespace(county_job_counts=AsyncMock(side_effect=[[counts(jobs=1)], [counts()]])),
            dzs_imports=SimpleNamespace(get_latest_succeeded=AsyncMock(return_value=None)),
            dzs_indicator_values=SimpleNamespace(list_values=AsyncMock(return_value=[])),
        )
        self.active = 0

        @asynccontextmanager
        async def open_work():
            self.active += 1
            try:
                yield self.work
            finally:
                self.active -= 1

        self.service = CountyIndicatorServiceFactory(Settings(_env_file=None)).create(open_work)

    async def test_filtered_counts_and_county_wide_counts_remain_separate_without_dzs(self) -> None:
        compared = await self.service.compare_counties(CountyComparisonRequestDTO(
            counties=(COUNTY.code, OTHER.name), filters=JobCountFiltersDTO(query="kuharica", full_time=False)))
        filtered, everything = [call.args[0] for call in self.work.jobs.county_job_counts.call_args_list]
        self.assertEqual((filtered.terms, filtered.full_time, filtered.county_ids), (("kuhar",), False, (1, 2)))
        self.assertEqual((everything.terms, everything.full_time), ((), None))
        self.assertEqual((compared.counties[0].filtered_jobs.jobs, compared.counties[0].all_active_jobs.jobs), (1, 5))
        self.assertEqual(compared.counties[0].unemployed_per_worker.unavailable_reason, "no_dzs_data")
        self.assertEqual([county.code for county in compared.counties], [COUNTY.code, OTHER.code])
        self.assertEqual(self.active, 0)

    async def test_county_aliases_cannot_select_the_same_county_twice(self) -> None:
        with self.assertRaisesRegex(InvalidIndicatorRequestError, "different counties"):
            await self.service.compare_counties(CountyComparisonRequestDTO(counties=(COUNTY.code, COUNTY.name)))
        self.work.jobs.county_job_counts.assert_not_called()
        self.assertEqual(self.active, 0)
