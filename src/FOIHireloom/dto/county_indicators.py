"""County comparisons of HZZ job ads with DZS registered unemployment, and the DZS unemployment rate over time.

Numbers that DZS publishes or that are computed from it are Decimal in
Python and JSON numbers in tool results: whole numbers for persons, one
decimal for rates and ratios. A value that cannot be given is null with a
machine-readable reason, never 0 or infinity.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, PlainSerializer, field_validator

from .base import ModelConfigBaseModel
from .dzs import DzsImportProvenanceDTO, DzsIndicator, DzsMissingReason, DzsSex, DzsValueSource
from .job_market import MARKET_WINDOW_DAYS, JobCountFiltersDTO
from .job_search import ActiveFilterDTO, CoverageDTO, DataStatus

MIN_COMPARED_COUNTIES = 2
MAX_COMPARED_COUNTIES = 6
MAX_HISTORY_COUNTIES = 6
MIN_HISTORY_MONTHS = 12
MAX_HISTORY_MONTHS = 24
DEFAULT_HISTORY_MONTHS = 12
MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


# A Decimal that tool results carry as a JSON number.
Number = Annotated[Decimal, PlainSerializer(_number, return_type=int | float, when_used="json")]

# no_dzs_data: no DZS import has succeeded, or none stored this indicator for
# the counties. no_common_period: no month has a known value for every
# compared county. dzs_value_missing: the county has no known value for the
# reference month (missing_reason then says how DZS marked it, if it did).
# no_hzz_data: none of the county's HZZ feeds has ever been loaded.
# no_known_workers: the county has active ads, but none states how many
# workers it seeks. zero_denominator: the denominator is a known 0.
type UnavailableReason = Literal[
    "no_dzs_data", "no_common_period", "dzs_value_missing", "no_hzz_data", "no_known_workers", "zero_denominator",
]


def parse_month(value: object) -> object:
    """"2026-09" as the first day of that month; a date must already be one."""
    if isinstance(value, str):
        if not (match := MONTH.fullmatch(value.strip())):
            raise ValueError("A month must be written as YYYY-MM, e.g. 2026-09.")
        return date(int(match[1]), int(match[2]), 1)
    if isinstance(value, date) and value.day != 1:
        raise ValueError("A month is given by its first day.")
    return value


class CountyComparisonRequestDTO(ModelConfigBaseModel):
    """What to compare: county codes or names as list_regions gives them, the job filters and the DZS month.

    filters choose the ads counted in each county's filtered_jobs only.
    period, the first day of a month or "YYYY-MM", fixes the DZS reference
    month for every indicator; without it each indicator uses the latest
    month for which every compared county has a known value.
    """

    counties: tuple[str, ...]
    filters: JobCountFiltersDTO = JobCountFiltersDTO()
    period: date | None = None

    _period = field_validator("period", mode="before")(parse_month)


class UnemploymentHistoryRequestDTO(ModelConfigBaseModel):
    """Counties as for a comparison, how many months to show and whose unemployment rate."""

    counties: tuple[str, ...]
    months: int = Field(default=DEFAULT_HISTORY_MONTHS, ge=MIN_HISTORY_MONTHS, le=MAX_HISTORY_MONTHS)
    sex: DzsSex = "total"


class ShareDTO(ModelConfigBaseModel):
    """part of whole as a percentage with one decimal; percent is None when whole is 0."""

    part: int
    whole: int
    percent: Number | None


class CountyJobCountsDTO(ModelConfigBaseModel):
    """Counts over one county's listed HZZ ads, as of the last HZZ sync.

    workers_needed sums only the ads whose HZZ page states the number of
    workers; workers_needed_coverage is those ads out of jobs. An unknown
    number is not 0. permanent_share is the ads with a permanent contract
    (na neodređeno) out of the ads whose contract is known, and
    contract_coverage those ads out of jobs. closing_soon counts ads whose
    deadline falls within window_days days, today included.
    """

    jobs: int
    workers_needed: int
    workers_needed_coverage: ShareDTO
    permanent_share: ShareDTO
    contract_coverage: ShareDTO
    closing_soon: int


class DzsCountyValueDTO(ModelConfigBaseModel):
    """One DZS value of a county for its reference month, sex total.

    value is persons for unemployed and active_population (exact counts from
    the DZS release table T1 or workbook sheet 9.4.13) and a percentage with
    one decimal for unemployment_rate. period is the reference month (its
    first day), None when no month could be chosen. is_provisional is DZS's
    own mark; months of 2026 are provisional. When value is None,
    unavailable_reason says why and missing_reason how DZS marked the cell,
    if the county has a row for that month.
    """

    indicator: DzsIndicator
    value: Number | None
    period: date | None
    is_provisional: bool | None
    source: DzsValueSource | None
    unavailable_reason: UnavailableReason | None
    missing_reason: DzsMissingReason | None = None


class CountyIndicatorDTO(ModelConfigBaseModel):
    """A ratio for a county as a whole, rounded to one decimal, with the numbers it was computed from.

    numerator and denominator are the values used, each None when unknown;
    value is None, with unavailable_reason, when either is unknown or the
    denominator is 0. dzs_period and is_provisional belong to its DZS value.
    """

    value: Number | None
    numerator: int | None
    denominator: int | None
    dzs_period: date | None
    is_provisional: bool | None
    unavailable_reason: UnavailableReason | None


class ComparedCountyDTO(ModelConfigBaseModel):
    """One compared county.

    filtered_jobs counts the ads matching the comparison's job filters.
    all_active_jobs counts every listed ad of the county whose deadline has
    not passed, whatever the filters; the indicators use it, because they
    describe the county as a whole, never one occupation or set of
    conditions. unemployed_per_worker is registered unemployed (DZS, exact
    count) divided by all_active_jobs.workers_needed, so its denominator
    covers only all_active_jobs.workers_needed_coverage of the ads.
    jobs_per_1000_active is all_active_jobs.jobs per 1,000 people of the
    DZS active population. hzz_data_status and hzz_last_success_at say how
    current the county's HZZ ads are, as in RegionFreshnessDTO.
    """

    code: str
    name: str
    iso_code: str
    hzz_data_status: DataStatus
    hzz_last_success_at: datetime | None
    filtered_jobs: CountyJobCountsDTO
    all_active_jobs: CountyJobCountsDTO
    unemployed: DzsCountyValueDTO
    active_population: DzsCountyValueDTO
    unemployment_rate: DzsCountyValueDTO
    unemployed_per_worker: CountyIndicatorDTO
    jobs_per_1000_active: CountyIndicatorDTO


class DzsReferencePeriodDTO(ModelConfigBaseModel):
    """The month one DZS indicator is compared in; None, with the reason, when no month could be chosen.

    requested is True when the caller fixed the month; a county without a
    value then is unavailable for it rather than shown for another month.
    """

    indicator: DzsIndicator
    period: date | None
    requested: bool
    unavailable_reason: UnavailableReason | None


class SourceDTO(ModelConfigBaseModel):
    """A data source named in a result; url is None for a local file."""

    name: str
    url: str | None
    description: str


class CountyComparisonDTO(ModelConfigBaseModel):
    """Counties side by side: HZZ ads matching the filters, county-wide HZZ totals, DZS values and two indicators.

    today is the day in Croatia the deadlines are compared with.
    hzz_coverage says how current the compared counties' ads are; its
    data_as_of is the oldest last successful HZZ sync among them. dzs is
    None when no DZS import has succeeded: the HZZ counts are still given,
    and every DZS value and indicator is unavailable with 'no_dzs_data'.
    dzs_periods is the reference month of each DZS indicator, which may
    differ between indicators. filters are the job filters as given;
    active_filters name the set ones in Croatian, as the views label them.
    HZZ counts are as of the last sync and DZS values for a past month, so
    the two refer to different moments; notes say this and the other
    limits, in English, for the LLM to pass on.
    """

    counties: tuple[ComparedCountyDTO, ...]
    today: date
    window_days: int = MARKET_WINDOW_DAYS
    filters: JobCountFiltersDTO
    active_filters: tuple[ActiveFilterDTO, ...] = ()
    requested_period: date | None
    dzs_periods: tuple[DzsReferencePeriodDTO, ...]
    hzz_coverage: CoverageDTO
    dzs: DzsImportProvenanceDTO | None
    sources: tuple[SourceDTO, ...]
    notes: tuple[str, ...]


class UnemploymentPointDTO(ModelConfigBaseModel):
    """The registered unemployment rate of one month, in percent with one decimal.

    rate is None, with unavailable_reason 'dzs_value_missing', when DZS has
    no known value for the month; missing_reason then says how DZS marked
    it, if it did. is_provisional is None without a stored row.
    """

    period: date
    rate: Number | None
    is_provisional: bool | None
    unavailable_reason: UnavailableReason | None = None
    missing_reason: DzsMissingReason | None = None


class CountyUnemploymentHistoryDTO(ModelConfigBaseModel):
    """One county's monthly unemployment rate, oldest month first, and the change over a year.

    latest is the last month of the series; same_month_previous_year the
    same month a year earlier. change_pp is latest minus that, in percentage
    points with one decimal; it is None, with change_unavailable_reason,
    when either rate is unknown.
    """

    code: str
    name: str
    iso_code: str
    series: tuple[UnemploymentPointDTO, ...]
    latest: UnemploymentPointDTO | None
    same_month_previous_year: UnemploymentPointDTO | None
    change_pp: Number | None
    change_unavailable_reason: UnavailableReason | None


class UnemploymentHistoryDTO(ModelConfigBaseModel):
    """The DZS registered unemployment rate of the requested counties over the last months.

    The series end at last_period, the latest month with a known rate for
    every requested county and sex, and start months - 1 months earlier at
    first_period. Without such a month, or without any succeeded DZS import,
    both are None, every series is empty and unavailable_reason says why.
    """

    counties: tuple[CountyUnemploymentHistoryDTO, ...]
    sex: DzsSex
    months: int
    first_period: date | None
    last_period: date | None
    unavailable_reason: UnavailableReason | None
    dzs: DzsImportProvenanceDTO | None
    sources: tuple[SourceDTO, ...]
    notes: tuple[str, ...]


class SourceLinkDTO(ModelConfigBaseModel):
    """A source as a view names it in Croatian; url is None for a local file."""

    label: str
    url: str | None


class DzsCountyValueViewDTO(DzsCountyValueDTO):
    """A DZS value with why it is unavailable in Croatian, e.g. "DZS nema podatak za rujan 2025."; None when known."""

    unavailable_label: str | None


class CountyIndicatorViewDTO(CountyIndicatorDTO):
    """An indicator with why it is unavailable in Croatian, e.g. "nijedan aktivni oglas ne navodi broj traženih
    radnika"; None when known."""

    unavailable_label: str | None


class ComparedCountyViewDTO(ComparedCountyDTO):
    """A compared county with its short name ("Varaždinska") and Croatian reasons for unavailable values."""

    short_name: str
    unemployed: DzsCountyValueViewDTO
    active_population: DzsCountyValueViewDTO
    unemployment_rate: DzsCountyValueViewDTO
    unemployed_per_worker: CountyIndicatorViewDTO
    jobs_per_1000_active: CountyIndicatorViewDTO


class CountyComparisonViewDTO(CountyComparisonDTO):
    """A county comparison for the county comparison view, with the Croatian wording it shows; the English fields stay.

    description names the query and the day the ads are counted on; the
    other filters are active_filters. coverage_note is hzz_coverage.warning
    in Croatian, None when every county is fresh. source_links name the
    sources, view_notes say the limits in Croatian and disclaimer that the
    indicators describe HZZ ads and registered unemployment only.
    """

    title: str
    description: str
    counties: tuple[ComparedCountyViewDTO, ...]
    coverage_note: str | None
    source_links: tuple[SourceLinkDTO, ...]
    view_notes: tuple[str, ...]
    disclaimer: str


class CountyUnemploymentHistoryViewDTO(CountyUnemploymentHistoryDTO):
    """A county's series with its short name and why change_pp is unavailable in Croatian, None when it is known."""

    short_name: str
    change_unavailable_label: str | None


class UnemploymentHistoryViewDTO(UnemploymentHistoryDTO):
    """Unemployment history for the unemployment history view, with the Croatian wording it shows.

    title names whose rate it is, description the months shown.
    unavailable_label says in Croatian why there is no series, None when
    there is one. source_links and view_notes are as in
    CountyComparisonViewDTO.
    """

    title: str
    description: str
    counties: tuple[CountyUnemploymentHistoryViewDTO, ...]
    unavailable_label: str | None
    source_links: tuple[SourceLinkDTO, ...]
    view_notes: tuple[str, ...]
