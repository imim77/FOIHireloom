from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import (
    MAX_COMPARED_COUNTIES,
    MAX_HISTORY_COUNTIES,
    MIN_COMPARED_COUNTIES,
    ComparedCountyDTO,
    CountyComparisonDTO,
    CountyComparisonRequestDTO,
    CountyIndicatorDTO,
    CountyJobCountsDTO,
    CountyUnemploymentHistoryDTO,
    DzsCountyValueDTO,
    DzsReferencePeriodDTO,
    ShareDTO,
    SourceDTO,
    UnavailableReason,
    UnemploymentHistoryDTO,
    UnemploymentHistoryRequestDTO,
    UnemploymentPointDTO,
)
from FOIHireloom.dto.dzs import DzsImportProvenanceDTO, DzsIndicator, DzsStoredValueDTO
from FOIHireloom.dto.job_market import CountyJobCountsRowDTO, CountyJobCriteriaDTO
from FOIHireloom.dto.job_search import RegionFreshnessDTO
from FOIHireloom.exceptions import InvalidIndicatorRequestError
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface

from .croatian_counties import CroatianCountyCatalog
from .feed_coverage import FeedCoverage
from .job_search import condition_criteria, local_date, search_terms

# The DZS values a comparison shows, each in its own reference month.
COMPARED_INDICATORS: tuple[DzsIndicator, ...] = ("unemployed", "active_population", "unemployment_rate")
ONE_DECIMAL = Decimal("0.1")

HZZ_SOURCE = SourceDTO(
    name="HZZ", url="https://burzarada.hzz.hr",
    description="Job advertisements of the Croatian Employment Service (HZZ), from its county RSS feeds and job "
                "pages, as stored at the last successful sync.",
)
DZS_FILES = {
    "t1": ("DZS release table T1", "Exact registered unemployed, active population and unemployment rate by "
                                   "county for the release's months."),
    "workbook": ("DZS county workbook", "Monthly active population (sheet 9.4.13) and registered unemployment "
                                        "rate (sheet 9.4.14) by county since 2020."),
}
NOTE_SCOPE = ("These indicators describe HZZ job advertisements and registered unemployment as DZS publishes it, not "
              "the whole labour market, and say nothing about anyone's personal chance of finding a job.")
NOTE_COUNTY_WIDE = ("unemployed_per_worker and jobs_per_1000_active describe each county as a whole: they use all its "
                    "active HZZ ads (all_active_jobs), never the job filters, which apply to filtered_jobs only. Do "
                    "not divide the unemployed by the ads of one occupation.")
NOTE_WORKERS = ("workers_needed counts only the ads whose HZZ page states it (workers_needed_coverage), so "
                "unemployed_per_worker is higher when fewer ads state it.")
NOTE_MOMENTS = ("HZZ counts are as of the last HZZ sync (hzz_coverage.data_as_of), DZS values are for a past "
                "reference month (dzs_periods); the two refer to different moments.")
NOTE_PROVISIONAL = "DZS values for months of 2026 are provisional and may be revised (is_provisional)."
NOTE_RATE = ("The rate is the registered unemployment rate: registered unemployed as a percentage of the active "
             "population, as DZS publishes it.")
NOTE_SEASONALITY = ("Comparing with the same month a year earlier reduces the effect of seasonality, which is strong "
                    "in coastal counties, but it is not a seasonal adjustment of the data.")


class CountyIndicatorService(CountyIndicatorServiceInterface):
    """County indicators from stored HZZ ads and DZS values, each with the period and coverage it rests on.

    A value that is missing, or a ratio whose numerator or denominator is
    unknown or whose denominator is 0, is reported as unavailable with a
    reason; nothing is replaced by 0 or by another month's value.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        counties: CroatianCountyCatalog,
        stale_after: timedelta = timedelta(hours=6),
    ) -> None:
        self._uow_factory = uow_factory
        self._counties = counties
        self._feed_coverage = FeedCoverage(stale_after)

    async def compare_counties(self, request: CountyComparisonRequestDTO) -> CountyComparisonDTO:
        self._check_count(request.counties, MIN_COMPARED_COUNTIES, MAX_COMPARED_COUNTIES)
        filters = request.filters
        terms = search_terms(filters.query)
        conditions = condition_criteria(filters)
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            today = local_date(now)
            counties = await self._resolve(work, request.counties)
            ids = tuple(county.id for county in counties)
            filtered = await work.jobs.county_job_counts(CountyJobCriteriaDTO(
                terms=terms, category=(filters.category or "").strip() or None,
                open_on=None if filters.include_expired else today, **conditions, county_ids=ids, today=today,
            ))
            # The indicators describe the county as a whole: every active ad, whatever the filters.
            everything = await work.jobs.county_job_counts(CountyJobCriteriaDTO(
                open_on=today, county_ids=ids, today=today))
            checks = await work.counties.list_feed_checks()
            provenance = await work.dzs_imports.get_latest_succeeded()
            periods = await self._reference_periods(work, provenance, request.period, ids)
            months = {reference.period for reference in periods.values() if reference.period is not None}
            stored = await work.dzs_indicator_values.list_values(ids, COMPARED_INDICATORS, "total", months)
        codes = {county.code for county in counties}
        regions = {region.code: region for region in self._feed_coverage.freshness(checks, now) if region.code in codes}
        compared_regions = [regions[county.code] for county in counties if county.code in regions]
        values = {(value.county_id, value.indicator): value for value in stored
                  if value.period == periods[value.indicator].period}
        filtered_by_county = {row.county_id: row for row in filtered}
        everything_by_county = {row.county_id: row for row in everything}
        return CountyComparisonDTO(
            counties=tuple(
                self._compared_county(county, regions.get(county.code), filtered_by_county.get(county.id),
                                      everything_by_county.get(county.id), periods, values)
                for county in counties
            ),
            today=today,
            filters=filters,
            requested_period=request.period,
            dzs_periods=tuple(periods.values()),
            hzz_coverage=self._feed_coverage.coverage(compared_regions),
            dzs=provenance,
            sources=self._sources(provenance),
            notes=(NOTE_SCOPE, NOTE_COUNTY_WIDE, NOTE_WORKERS, NOTE_MOMENTS, NOTE_PROVISIONAL),
        )

    async def unemployment_history(self, request: UnemploymentHistoryRequestDTO) -> UnemploymentHistoryDTO:
        self._check_count(request.counties, 1, MAX_HISTORY_COUNTIES)
        async with self._uow_factory() as work:
            counties = await self._resolve(work, request.counties)
            ids = tuple(county.id for county in counties)
            provenance = await work.dzs_imports.get_latest_succeeded()
            last = None
            if provenance is not None:
                latest = await work.dzs_indicator_values.latest_common_periods(ids, ("unemployment_rate",), request.sex)
                last = latest.get("unemployment_rate")
            stored: list[DzsStoredValueDTO] = []
            if last is not None:
                first = add_months(last, 1 - request.months)
                previous_year = add_months(last, -12)
                stored = await work.dzs_indicator_values.list_series(
                    ids, "unemployment_rate", request.sex, min(first, previous_year), last)
        notes = (NOTE_RATE, NOTE_SEASONALITY, NOTE_PROVISIONAL)
        if last is None:
            reason: UnavailableReason = "no_dzs_data" if provenance is None else "no_common_period"
            return UnemploymentHistoryDTO(
                counties=tuple(
                    CountyUnemploymentHistoryDTO(
                        code=county.code, name=county.name, iso_code=county.iso_code, series=(), latest=None,
                        same_month_previous_year=None, change_pp=None, change_unavailable_reason=reason,
                    )
                    for county in counties
                ),
                sex=request.sex, months=request.months, first_period=None, last_period=None,
                unavailable_reason=reason, dzs=provenance, sources=self._sources(provenance, with_hzz=False),
                notes=notes,
            )
        rates = {(value.county_id, value.period): value for value in stored}
        window = [add_months(first, offset) for offset in range(request.months)]
        return UnemploymentHistoryDTO(
            counties=tuple(self._history(county, rates, window, previous_year) for county in counties),
            sex=request.sex, months=request.months, first_period=first, last_period=last, unavailable_reason=None,
            dzs=provenance, sources=self._sources(provenance, with_hzz=False), notes=notes,
        )

    @staticmethod
    def _check_count(counties: Sequence[str], least: int, most: int) -> None:
        if not least <= len(counties) <= most:
            raise InvalidIndicatorRequestError(f"Choose {least} to {most} counties, not {len(counties)}.")

    async def _resolve(self, work: UnitOfWork, requested: Sequence[str]) -> list[CountyDTO]:
        """The stored counties by code or name, in the given order; raise for unknown or repeated ones."""
        stored = {county.code: county for county in await work.counties.list_all()}
        resolved: list[CountyDTO] = []
        unknown: list[str] = []
        for label in requested:
            definition = self._counties.match(label)
            code = definition.code if definition is not None else label.strip().casefold()
            if code in stored:
                resolved.append(stored[code])
            else:
                unknown.append(label)
        if unknown:
            raise InvalidIndicatorRequestError(
                f"Unknown {'county' if len(unknown) == 1 else 'counties'}: {', '.join(unknown)}. Use county codes "
                f"or names from list_regions: {', '.join(sorted(stored))}.")
        codes = [county.code for county in resolved]
        if repeated := sorted({code for code in codes if codes.count(code) > 1}):
            raise InvalidIndicatorRequestError(
                f"Choose different counties; given more than once: {', '.join(repeated)}.")
        return resolved

    @staticmethod
    async def _reference_periods(
        work: UnitOfWork, provenance: DzsImportProvenanceDTO | None, requested: date | None, county_ids: Sequence[int],
    ) -> dict[DzsIndicator, DzsReferencePeriodDTO]:
        """Each indicator's month: the requested one, else the latest with a known value for every county."""
        if provenance is None:
            return {indicator: DzsReferencePeriodDTO(indicator=indicator, period=None, requested=requested is not None,
                                                     unavailable_reason="no_dzs_data")
                    for indicator in COMPARED_INDICATORS}
        if requested is not None:
            return {indicator: DzsReferencePeriodDTO(indicator=indicator, period=requested, requested=True,
                                                     unavailable_reason=None)
                    for indicator in COMPARED_INDICATORS}
        latest = await work.dzs_indicator_values.latest_common_periods(county_ids, COMPARED_INDICATORS, "total")
        return {
            indicator: DzsReferencePeriodDTO(
                indicator=indicator, period=latest.get(indicator), requested=False,
                unavailable_reason=None if indicator in latest else "no_common_period",
            )
            for indicator in COMPARED_INDICATORS
        }

    def _compared_county(
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
        # A county none of whose feeds was ever loaded has no known ads, not zero ads.
        hzz_known = region is not None and region.last_success_at is not None
        workers: int | None = all_active.workers_needed if all_active.workers_needed_coverage.part else None
        workers_reason: UnavailableReason | None = None
        if not hzz_known:
            workers, workers_reason = None, "no_hzz_data"
        elif all_active.jobs and workers is None:
            workers_reason = "no_known_workers"
        elif not all_active.jobs:
            # No active ads: the county seeks no workers through HZZ.
            workers = 0
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
    def _history(
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

    @staticmethod
    def _sources(provenance: DzsImportProvenanceDTO | None, *, with_hzz: bool = True) -> tuple[SourceDTO, ...]:
        """HZZ, and each DZS file of the latest succeeded import; a local file has no URL."""
        files = provenance.files if provenance is not None else ()
        dzs = []
        for file in files:
            name, description = DZS_FILES[file.role]
            if file.location.startswith(("https://", "http://")):
                dzs.append(SourceDTO(name=name, url=file.location, description=description))
            else:
                dzs.append(SourceDTO(name=name, url=None, description=f"{description} Read from the local file "
                                                                      f"{file.location}."))
        return (HZZ_SOURCE, *dzs) if with_hzz else tuple(dzs)


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


def add_months(month: date, months: int) -> date:
    """The first day of the month that many months after month's (before, when negative)."""
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)
