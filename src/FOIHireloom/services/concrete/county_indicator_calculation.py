from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import (
    ComparedCountyDTO, CountyIndicatorDTO, CountyJobCountsDTO, CountyUnemploymentHistoryDTO,
    DzsCountyValueDTO, DzsReferencePeriodDTO, ShareDTO, UnavailableReason, UnemploymentPointDTO,
)
from FOIHireloom.dto.dzs import DzsIndicator, DzsStoredValueDTO
from FOIHireloom.dto.job_market import CountyJobCountsRowDTO
from FOIHireloom.dto.job_search import RegionFreshnessDTO

COMPARED_INDICATORS: tuple[DzsIndicator, ...] = ("unemployed", "active_population", "unemployment_rate")
ONE_DECIMAL = Decimal("0.1")


class CountyIndicatorCalculator:
    """CountyIndicatorCalculator derives county ratios and monthly changes.

    Missing observations stay unavailable with their original reason;
    a missing denominator is never treated as zero.
    """

    def compare(
        self,
        county: CountyDTO,
        region: RegionFreshnessDTO | None,
        filtered: CountyJobCountsRowDTO | None,
        everything: CountyJobCountsRowDTO | None,
        periods: Mapping[DzsIndicator, DzsReferencePeriodDTO],
        values: Mapping[tuple[int, DzsIndicator], DzsStoredValueDTO],
    ) -> ComparedCountyDTO:
        dzs = {indicator: self._dzs_value(periods[indicator], values.get((county.id, indicator)))
               for indicator in COMPARED_INDICATORS}
        all_active = self._job_counts(everything, county.id)
        hzz_known = region is not None and region.last_success_at is not None
        workers, workers_reason = self._workers_needed(all_active, hzz_known)
        return ComparedCountyDTO(
            code=county.code, name=county.name, iso_code=county.iso_code,
            hzz_data_status=region.data_status if region is not None else "unavailable",
            hzz_last_success_at=region.last_success_at if region is not None else None,
            filtered_jobs=self._job_counts(filtered, county.id),
            all_active_jobs=all_active,
            unemployed=dzs["unemployed"],
            active_population=dzs["active_population"],
            unemployment_rate=dzs["unemployment_rate"],
            unemployed_per_worker=self._ratio(dzs["unemployed"], workers, workers_reason, dzs_is_numerator=True),
            jobs_per_1000_active=self._ratio(dzs["active_population"], all_active.jobs if hzz_known else None,
                                             None if hzz_known else "no_hzz_data", dzs_is_numerator=False,
                                             scale=1000),
        )

    @staticmethod
    def _workers_needed(
        all_active: CountyJobCountsDTO, hzz_known: bool,
    ) -> tuple[int | None, UnavailableReason | None]:
        """The workers the county's active ads seek, or None with the reason they are unknown."""
        if not hzz_known:
            return None, "no_hzz_data"
        if not all_active.jobs:
            return 0, None
        if not all_active.workers_needed_coverage.part:
            return None, "no_known_workers"
        return all_active.workers_needed, None

    @staticmethod
    def _job_counts(row: CountyJobCountsRowDTO | None, county_id: int) -> CountyJobCountsDTO:
        row = row or CountyJobCountsRowDTO(county_id=county_id, jobs=0, with_workers_needed=0, workers_needed=0,
                                           with_contract=0, permanent=0, closing_soon=0)
        return CountyJobCountsDTO(
            jobs=row.jobs,
            workers_needed=row.workers_needed,
            workers_needed_coverage=share(row.with_workers_needed, row.jobs),
            permanent_share=share(row.permanent, row.with_contract),
            contract_coverage=share(row.with_contract, row.jobs),
            closing_soon=row.closing_soon,
        )

    @staticmethod
    def _dzs_value(reference: DzsReferencePeriodDTO, stored: DzsStoredValueDTO | None) -> DzsCountyValueDTO:
        if reference.period is None:
            return DzsCountyValueDTO(indicator=reference.indicator, value=None, period=None, is_provisional=None,
                                     source=None, unavailable_reason=reference.unavailable_reason)
        if stored is None:
            return DzsCountyValueDTO(indicator=reference.indicator, value=None, period=reference.period,
                                     is_provisional=None, source=None, unavailable_reason="dzs_value_missing")
        return DzsCountyValueDTO(
            indicator=reference.indicator, value=stored.value, period=stored.period,
            is_provisional=stored.is_provisional, source=stored.source,
            unavailable_reason=None if stored.value is not None else "dzs_value_missing",
            missing_reason=stored.missing_reason,
        )

    @staticmethod
    def _ratio(
        dzs: DzsCountyValueDTO, hzz: int | None, hzz_reason: UnavailableReason | None, *, dzs_is_numerator: bool,
        scale: int = 1,
    ) -> CountyIndicatorDTO:
        """dzs / hzz or hzz / dzs, times scale; the DZS side's reason comes first when both are unknown."""
        dzs_number = None if dzs.value is None else int(dzs.value)
        numerator, denominator = (dzs_number, hzz) if dzs_is_numerator else (hzz, dzs_number)
        reason = dzs.unavailable_reason or hzz_reason
        if reason is None and denominator == 0:
            reason = "zero_denominator"
        value = None
        if reason is None and numerator is not None and denominator:
            value = (Decimal(numerator) * scale / Decimal(denominator)).quantize(ONE_DECIMAL, ROUND_HALF_UP)
        return CountyIndicatorDTO(value=value, numerator=numerator, denominator=denominator, dzs_period=dzs.period,
                                  is_provisional=dzs.is_provisional, unavailable_reason=reason)

    @staticmethod
    def history(
        county: CountyDTO, rates: Mapping[tuple[int, date], DzsStoredValueDTO], window: Sequence[date],
        previous_year: date,
    ) -> CountyUnemploymentHistoryDTO:
        series = tuple(point(period, rates.get((county.id, period))) for period in window)
        latest = series[-1]
        before = point(previous_year, rates.get((county.id, previous_year)))
        known = latest.rate is not None and before.rate is not None
        return CountyUnemploymentHistoryDTO(
            code=county.code, name=county.name, iso_code=county.iso_code, series=series, latest=latest,
            same_month_previous_year=before,
            change_pp=(latest.rate - before.rate).quantize(ONE_DECIMAL) if known else None,
            change_unavailable_reason=None if known else "dzs_value_missing",
        )


def share(part: int, whole: int) -> ShareDTO:
    percent = (Decimal(part) * 100 / Decimal(whole)).quantize(ONE_DECIMAL, ROUND_HALF_UP) if whole else None
    return ShareDTO(part=part, whole=whole, percent=percent)


def point(period: date, stored: DzsStoredValueDTO | None) -> UnemploymentPointDTO:
    if stored is None:
        return UnemploymentPointDTO(period=period, rate=None, is_provisional=None, unavailable_reason="dzs_value_missing")
    return UnemploymentPointDTO(
        period=period, rate=stored.value, is_provisional=stored.is_provisional,
        unavailable_reason=None if stored.value is not None else "dzs_value_missing",
        missing_reason=stored.missing_reason,
    )
