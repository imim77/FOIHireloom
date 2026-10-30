from datetime import date

from pydantic import Field

from .base import ModelConfigBaseModel
from .job_search import MAX_QUERY_LENGTH, CoverageDTO, JobFilterCriteriaDTO

# Days, today included, counted as "recent" and "closing soon".
MARKET_WINDOW_DAYS = 7
DEFAULT_MARKET_TOP = 10
MAX_MARKET_TOP = 50


class JobMarketFiltersDTO(ModelConfigBaseModel):
    """The jobs to count, chosen as JobSearchFiltersDTO chooses jobs to list.

    top is the length of the employer, working hours and experience breakdowns.
    """

    query: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    county: str | None = None
    category: str | None = None
    include_expired: bool = False
    top: int = Field(default=DEFAULT_MARKET_TOP, ge=1, le=MAX_MARKET_TOP)


class JobMarketCriteriaDTO(JobFilterCriteriaDTO):
    """Filters plus the day the time windows start from and the length of long breakdowns.

    top limits the employer, working hours and experience breakdowns; the
    others have few values and are complete.
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

    categories cover only the with_category jobs: the category comes from the
    feed's description suffix, which HZZ cuts off in about half of the jobs.
    Fields read from the job page (workers_needed, employers, employment_types,
    working_hours, education, experience, accommodation) cover only the
    with_details jobs whose page was read. A job can list several employment
    types and education levels, so those counts may add up to more than jobs.
    Values a job does not state are left out of the breakdowns.
    published_recently and closing_soon count jobs published, or whose
    deadline falls, within MARKET_WINDOW_DAYS days of today.
    """

    jobs: int
    with_details: int
    with_category: int
    workers_needed: int
    published_recently: int
    closing_soon: int
    counties: tuple[CountyMarketCountDTO, ...]
    categories: tuple[MarketCountDTO, ...]
    employers: tuple[MarketCountDTO, ...]
    employment_types: tuple[MarketCountDTO, ...]
    working_hours: tuple[MarketCountDTO, ...]
    education: tuple[MarketCountDTO, ...]
    experience: tuple[MarketCountDTO, ...]
    accommodation: tuple[MarketCountDTO, ...]


class JobMarketStatsDTO(JobMarketAggregatesDTO):
    """Market statistics as of today (Europe/Zagreb) with the freshness of the counties they cover.

    When coverage is not fresh, the counts may be outdated or incomplete.
    """

    today: date
    window_days: int = MARKET_WINDOW_DAYS
    coverage: CoverageDTO


class CountyShareDTO(ModelConfigBaseModel):
    """One county's jobs; share is its percentage of all matching jobs."""

    code: str
    name: str
    short_name: str
    jobs: int
    workers_needed: int
    share: float


class JobsByCountyDTO(ModelConfigBaseModel):
    """Every county with matching jobs, most jobs first, for the jobs-by-county chart.

    The chart shows the first top counties and lets the user expand it to all.
    """

    title: str
    description: str
    today: date
    total_jobs: int
    total_workers_needed: int
    top: int
    counties: tuple[CountyShareDTO, ...]
    coverage: CoverageDTO
