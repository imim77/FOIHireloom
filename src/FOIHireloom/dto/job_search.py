import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, computed_field, field_validator

from .base import ModelConfigBaseModel

MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200
SEARCH_TERM = re.compile(r"[^\W_]+")

# fresh: every feed succeeded recently; stale: a feed's last success is too
# old; unavailable: there is no enabled feed or one has never succeeded.
type DataStatus = Literal["fresh", "stale", "unavailable"]


class JobSearchFiltersDTO(ModelConfigBaseModel):
    """What a caller asks for; county is a code from list_regions() or a county name.

    Jobs whose known deadline has passed are left out unless include_expired
    is set. Jobs without a deadline are always included.
    """

    query: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    county: str | None = None
    category: str | None = None
    include_expired: bool = False
    limit: int = Field(default=MAX_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    cursor: str | None = None


class JobCursorDTO(ModelConfigBaseModel):
    """Position after the last returned job in the search order."""

    published_on: date | None
    id: int = Field(ge=1, le=2**63 - 1)


class JobSearchCriteriaDTO(ModelConfigBaseModel):
    """Validated filters for the job repository.

    terms are ASCII-folded, lowercase words; each must match a word prefix.
    open_on leaves out jobs whose known deadline is before that day.
    """

    terms: tuple[str, ...] = ()
    county_id: int | None = None
    category: str | None = None
    open_on: date | None = None
    after: JobCursorDTO | None = None
    limit: int = Field(ge=1)

    @field_validator("terms")
    @classmethod
    def terms_are_single_words(cls, terms: tuple[str, ...]) -> tuple[str, ...]:
        # Terms are joined into a to_tsquery() expression, so operators must not get through.
        if not all(SEARCH_TERM.fullmatch(term) for term in terms):
            raise ValueError("Search terms must be single words without punctuation.")
        return terms


class JobSummaryDTO(ModelConfigBaseModel):
    """A search result; None means the source did not state the value.

    deadline_passed is None when the deadline is unknown. location_text and
    municipality come from the description suffix, which HZZ cuts off in
    about half of the jobs; county_name comes from the county feed that
    publishes the job and is known for every job in a feed.
    """

    id: int
    source_job_id: str | None
    title: str | None
    category: str | None
    location_text: str | None
    municipality: str | None
    county_code: str | None = None
    county_name: str | None = None
    published_on: date | None
    deadline_on: date | None
    deadline_passed: bool | None = None
    canonical_url: str
    quality_flags: tuple[str, ...]
    last_seen_at: datetime

    @computed_field
    @property
    def display_title(self) -> str:
        """The title, or a neutral label when the source gave none; never an invented job name."""
        if self.title is not None:
            return self.title
        return f"Oglas HZZ {self.source_job_id}" if self.source_job_id else f"Oglas HZZ bez naslova ({self.id})"

    @computed_field
    @property
    def display_location(self) -> str:
        """The place of work with its county; says so when HZZ gave only the county."""
        place = self.location_text or self.municipality
        if place and self.county_name:
            return f"{place}, {self.county_name}"
        if place:
            return place
        if self.county_name:
            return f"{self.county_name} (mjesto rada nije navedeno)"
        return "Mjesto rada nije navedeno"


class RegionFreshnessDTO(ModelConfigBaseModel):
    """How current the stored jobs of one county are.

    last_success_at is the oldest last successful check among the county's
    enabled feeds, or None if none has succeeded.
    """

    code: str
    name: str
    data_status: DataStatus
    last_success_at: datetime | None


class CoverageDTO(ModelConfigBaseModel):
    """Freshness of the counties a search covered.

    An empty or short result from a county that is not fresh does not show
    that the county has no such jobs.
    """

    data_status: DataStatus
    data_as_of: datetime | None
    stale_after_hours: float
    affected_regions: tuple[RegionFreshnessDTO, ...]
    warning: str | None


class JobSearchPageDTO(ModelConfigBaseModel):
    jobs: tuple[JobSummaryDTO, ...]
    next_cursor: str | None
    coverage: CoverageDTO


class JobListingDTO(ModelConfigBaseModel):
    """Where a job is published; missing means it left that feed, not that it closed.

    data_status describes the feed, so presence_status is only as current as
    feed_last_success_at.
    """

    county_code: str
    county_name: str
    presence_status: str
    first_seen_at: datetime
    last_seen_at: datetime
    missing_since_at: datetime | None
    feed_last_success_at: datetime | None
    data_status: DataStatus = "unavailable"


class JobDetailsDTO(JobSummaryDTO):
    """Stored content of one job; descriptions are cut by the source at 512 characters.

    availability_status stays unknown until there is evidence the job is open
    or closed. Dropping out of every feed is not such evidence.
    """

    description_text: str | None
    availability_status: str
    first_seen_at: datetime
    content_changed_at: datetime
    listings: tuple[JobListingDTO, ...] = ()


class RegionDTO(ModelConfigBaseModel):
    """A county and the number of its listed jobs whose deadline has not passed."""

    code: str
    name: str
    open_jobs: int
    data_status: DataStatus = "unavailable"
    last_success_at: datetime | None = None


class JobCountyDTO(ModelConfigBaseModel):
    """A county whose feed lists or listed a job."""

    job_id: int
    county_code: str
    county_name: str
    presence_status: str


class CountyFeedCheckDTO(ModelConfigBaseModel):
    """One enabled county feed's last success; feed_id is None for a county without one."""

    code: str
    name: str
    feed_id: int | None
    last_success_at: datetime | None


class CategoryDTO(ModelConfigBaseModel):
    name: str
    open_jobs: int
