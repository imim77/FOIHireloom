import re
from datetime import date, datetime

from pydantic import Field, field_validator

from .base import ModelConfigBaseModel

MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200
SEARCH_TERM = re.compile(r"[^\W_]+")


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

    deadline_passed is None when the deadline is unknown.
    """

    id: int
    title: str | None
    category: str | None
    location_text: str | None
    municipality: str | None
    published_on: date | None
    deadline_on: date | None
    deadline_passed: bool | None = None
    canonical_url: str
    quality_flags: tuple[str, ...]
    last_seen_at: datetime


class JobSearchPageDTO(ModelConfigBaseModel):
    jobs: tuple[JobSummaryDTO, ...]
    next_cursor: str | None


class JobListingDTO(ModelConfigBaseModel):
    """Where a job is published; missing means it left that feed, not that it closed."""

    county_code: str
    county_name: str
    presence_status: str
    first_seen_at: datetime
    last_seen_at: datetime
    missing_since_at: datetime | None


class JobDetailsDTO(JobSummaryDTO):
    """Stored content of one job; descriptions are cut by the source at 512 characters.

    availability_status stays unknown until there is evidence the job is open
    or closed. Dropping out of every feed is not such evidence.
    """

    source_job_id: str | None
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


class CategoryDTO(ModelConfigBaseModel):
    name: str
    open_jobs: int
