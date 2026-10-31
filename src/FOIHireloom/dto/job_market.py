from datetime import date
from typing import Literal

from pydantic import Field

from .base import ModelConfigBaseModel
from .job_search import MAX_QUERY_LENGTH, CoverageDTO, JobConditionFiltersDTO, JobFilterCriteriaDTO

# What the jobs-by-county chart ranks and draws the counties by.
type CountyMetric = Literal["jobs", "workers_needed"]

# Days, today included, counted as "recent" and "closing soon".
MARKET_WINDOW_DAYS = 7
DEFAULT_MARKET_TOP = 10
MAX_MARKET_TOP = 50


class JobMarketFiltersDTO(JobConditionFiltersDTO):
    """The jobs to count, chosen as JobSearchFiltersDTO chooses jobs to list.

    top is the length of the employers breakdown.
    """

    query: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    county: str | None = None
    category: str | None = None
    include_expired: bool = False
    top: int = Field(default=DEFAULT_MARKET_TOP, ge=1, le=MAX_MARKET_TOP)


class JobMarketCriteriaDTO(JobFilterCriteriaDTO):
    """Filters plus the day the time windows start from and the length of long breakdowns.

    top limits the employers breakdown; the others have few values and are complete.
    """

    today: date
    top: int = Field(ge=1)


class MarketCountDTO(ModelConfigBaseModel):
    """Jobs with one value of a field; workers_needed sums the positions their pages state."""

    name: str
    jobs: int
    workers_needed: int


class CountyMarketCountDTO(MarketCountDTO):
    code: str


class JobMarketAggregatesDTO(ModelConfigBaseModel):
    """Counts over the jobs matching JobMarketCriteriaDTO.

    categories cover only the with_category jobs, the sum of
    category_from_description (stated in the job's own description) and
    category_from_feed (filled in from an HZZ occupation feed whose category
    was verified on its jobs); the other jobs have no known category.
    workers_needed and employers are read from the job page and cover only
    the with_details jobs whose page was read. The other breakdowns count the
    page's normalised conditions, codes as in JobConditionsDTO, each over
    the jobs whose value is known: contracts, employment_tags, working_time
    ("full_time" or "part_time"), experience_bands ("none" is 0 months and
    includes trainee ads, then "1_to_12_months", "13_to_36_months" and
    "over_36_months"), education_levels (a job counts once per level it
    accepts), accommodation, schedule_tags and transport_allowance. A job can
    have several employment tags, education levels and schedule tags, so
    those counts may add up to more than jobs. Values a job does not state
    are left out of the breakdowns.
    published_recently and closing_soon count jobs published, or whose
    deadline falls, within MARKET_WINDOW_DAYS days of today.
    """

    jobs: int
    with_details: int
    with_category: int
    category_from_description: int
    category_from_feed: int
    workers_needed: int
    published_recently: int
    closing_soon: int
    counties: tuple[CountyMarketCountDTO, ...]
    categories: tuple[MarketCountDTO, ...]
    employers: tuple[MarketCountDTO, ...]
    contracts: tuple[MarketCountDTO, ...]
    employment_tags: tuple[MarketCountDTO, ...]
    working_time: tuple[MarketCountDTO, ...]
    experience_bands: tuple[MarketCountDTO, ...]
    education_levels: tuple[MarketCountDTO, ...]
    accommodation: tuple[MarketCountDTO, ...]
    schedule_tags: tuple[MarketCountDTO, ...]
    transport_allowance: tuple[MarketCountDTO, ...]


class JobMarketStatsDTO(JobMarketAggregatesDTO):
    """Market statistics as of today (Europe/Zagreb) with the freshness of the counties they cover.

    When coverage is not fresh, the counts may be outdated or incomplete.
    unknown_conditions and unknown_total are as in JobSearchPageDTO.
    """

    today: date
    window_days: int = MARKET_WINDOW_DAYS
    coverage: CoverageDTO
    unknown_conditions: dict[str, int] = {}
    unknown_total: int = 0


class CountyShareDTO(ModelConfigBaseModel):
    """One county's jobs; share is its percentage of all matching jobs."""

    code: str
    name: str
    short_name: str
    jobs: int
    workers_needed: int
    share: float


class JobsByCountyDTO(ModelConfigBaseModel):
    """Every county with matching jobs, for the jobs-by-county chart.

    Counties are ranked by metric, highest first; the chart draws that value
    as columns, shows the first top counties and lets the user expand it to all.
    unknown_conditions and unknown_total are as in JobSearchPageDTO.
    """

    metric: CountyMetric
    title: str
    description: str
    today: date
    total_jobs: int
    total_workers_needed: int
    top: int
    counties: tuple[CountyShareDTO, ...]
    coverage: CoverageDTO
    unknown_conditions: dict[str, int] = {}
    unknown_total: int = 0
