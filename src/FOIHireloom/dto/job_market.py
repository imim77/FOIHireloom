from datetime import date

from pydantic import Field

from .base import ModelConfigBaseModel
from .job_search import JobFilterCriteriaDTO

# Days, today included, counted as "recent" and "closing soon".
MARKET_WINDOW_DAYS = 7


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
