from collections.abc import Sequence
from datetime import date

from FOIHireloom.db.uow.base import UnitOfWork, UnitOfWorkFactory
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.dto.county_indicators import (
    MAX_COMPARED_COUNTIES,
    MAX_HISTORY_COUNTIES,
    MIN_COMPARED_COUNTIES,
    CountyComparisonDTO,
    CountyComparisonRequestDTO,
    CountyUnemploymentHistoryDTO,
    DzsReferencePeriodDTO,
    SourceDTO,
    UnavailableReason,
    UnemploymentHistoryDTO,
    UnemploymentHistoryRequestDTO,
)
from FOIHireloom.dto.dzs import DzsImportProvenanceDTO, DzsIndicator, DzsStoredValueDTO
from FOIHireloom.dto.job_market import CountyJobCriteriaDTO
from FOIHireloom.exceptions import InvalidIndicatorRequestError
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface

from .croatian_counties import CroatianCountyCatalog
from .feed_coverage import FeedCoverage
from FOIHireloom.domain.job_search import condition_criteria, local_date, search_terms

from .county_indicator_calculation import COMPARED_INDICATORS, CountyIndicatorCalculator

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
        uow_factory: UnitOfWorkFactory,
        counties: CroatianCountyCatalog,
        feed_coverage: FeedCoverage,
        calculator: CountyIndicatorCalculator,
    ) -> None:
        self._uow_factory = uow_factory
        self._counties = counties
        self._feed_coverage = feed_coverage
        self._calculator = calculator

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
                self._calculator.compare(county, regions.get(county.code), filtered_by_county.get(county.id),
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
            counties=tuple(self._calculator.history(county, rates, window, previous_year) for county in counties),
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


def add_months(month: date, months: int) -> date:
    """The first day of the month that many months after month's (before, when negative)."""
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)
