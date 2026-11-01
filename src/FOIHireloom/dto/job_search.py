import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, computed_field, field_validator

from .base import ModelConfigBaseModel
from .job_conditions import Contract, EducationLevel, EmploymentTag, JobConditionsDTO

MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200
# 50 years, well within the integer column.
MAX_EXPERIENCE_MONTHS = 600
SEARCH_TERM = re.compile(r"[^\W_]+")
PLACE_WORDS = re.compile(r"[^\W_]+(?: [^\W_]+)*")

# fresh: every feed succeeded recently; stale: a feed's last success is too
# old; unavailable: there is no enabled feed or one has never succeeded.
type DataStatus = Literal["fresh", "stale", "unavailable"]
# Whether the job's HZZ detail page was read; see Job.page_status.
type DetailsStatus = Literal["pending", "fetched", "unavailable", "failed"]


class CandidateConditionsDTO(ModelConfigBaseModel):
    """What a person states about their experience and education and the job they want; None leaves one out.

    A job meets max_experience_months, the person's experience, when it asks
    for at most that; "Nije važno" and trainee ads ask for 0. It meets
    contract and full_time when its own are the same. education is the
    person's level, met by a job that accepts it. accommodation True is met
    by a job offering any accommodation, False by one offering none. A job
    whose value is unknown, because its HZZ page was not read or does not
    state it, meets none of them.
    """

    max_experience_months: int | None = Field(default=None, ge=0, le=MAX_EXPERIENCE_MONTHS)
    contract: Contract | None = None
    full_time: bool | None = None
    education: EducationLevel | None = None
    accommodation: bool | None = None


class JobConditionFiltersDTO(CandidateConditionsDTO):
    """Filters on a job's normalised conditions and place of work; None leaves one out.

    A job whose value is unknown, because its HZZ page was not read or does
    not state it, never matches a filter on that value. max_experience_months=0
    finds "Nije važno" and trainee ads. education is the caller's level and
    matches jobs that accept it. accommodation True finds jobs offering any
    accommodation, False those offering none. A job must have every one of
    employment_tags. place matches the place of work on the job page, without
    the county after its comma, or the feed's municipality when the place's
    words appear there in a row as whole words, ignoring case and Croatian
    diacritics: "Pula" finds "PULA-POLA" and "Zagreb" "ZAGREB-DUBRAVA".
    """

    employment_tags: tuple[EmploymentTag, ...] | None = None
    place: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)


class JobSearchFiltersDTO(JobConditionFiltersDTO):
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
    """Position after the last returned job in the search order.

    title_match is set only for a search with a query, whose title matches come first.
    """

    title_match: bool | None = None
    published_on: date | None
    id: int = Field(ge=1, le=2**63 - 1)


class JobFilterCriteriaDTO(JobConditionFiltersDTO):
    """Validated filters for the job repository.

    terms are ASCII-folded, lowercase words or their stems; each must match a word prefix.
    open_on leaves out jobs whose known deadline is before that day. place
    holds the place's words folded the same way, joined by single spaces.
    """

    terms: tuple[str, ...] = ()
    county_id: int | None = None
    category: str | None = None
    open_on: date | None = None

    @field_validator("terms")
    @classmethod
    def terms_are_single_words(cls, terms: tuple[str, ...]) -> tuple[str, ...]:
        # Terms are joined into a to_tsquery() expression, so operators must not get through.
        if not all(SEARCH_TERM.fullmatch(term) for term in terms):
            raise ValueError("Search terms must be single words without punctuation.")
        return terms

    @field_validator("place")
    @classmethod
    def place_is_words(cls, place: str | None) -> str | None:
        # The place goes into a LIKE pattern, so wildcards must not get through.
        if place is not None and not PLACE_WORDS.fullmatch(place):
            raise ValueError("The place must be words separated by single spaces.")
        return place


class JobSearchCriteriaDTO(JobFilterCriteriaDTO):
    """Filters plus the page to return; after continues after a previous page."""

    after: JobCursorDTO | None = None
    limit: int = Field(ge=1)


class JobSummaryDTO(ModelConfigBaseModel):
    """A search result; None means the source did not state the value.

    Once the job's HZZ detail page has been read, title, deadline_on,
    work_place and employer_name come from it; deadline_on is then its
    "Natječaj vrijedi do" date. Otherwise they come from the feed, whose
    description suffix HZZ often cuts off. category is stated in that
    description (category_source 'description') or filled in from an HZZ
    occupation feed verified on its jobs ('feed'); both are None together.
    deadline_passed is None when the deadline is unknown. county_name comes
    from the county feed that publishes the job and is known for every job in
    a feed. title_match tells whether every query word matched the title;
    such jobs come first, and it is None for a search without a query.
    """

    id: int
    source_job_id: str | None
    title: str | None
    category: str | None
    category_source: Literal["description", "feed"] | None = None
    location_text: str | None
    municipality: str | None
    county_code: str | None = None
    county_name: str | None = None
    published_on: date | None
    deadline_on: date | None
    deadline_source: Literal["job_page", "feed"] | None = None
    deadline_passed: bool | None = None
    work_place: str | None = None
    employer_name: str | None = None
    canonical_url: str
    quality_flags: tuple[str, ...]
    details_status: DetailsStatus = "pending"
    title_match: bool | None = None
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
        if self.work_place:
            county = self.county_name
            # The page usually names the county already: "PULA-POLA, ISTARSKA ŽUPANIJA".
            return f"{self.work_place}, {county}" if county and county.upper() not in self.work_place else self.work_place
        place = self.location_text or self.municipality
        if place and self.county_name:
            return f"{place}, {self.county_name}"
        if place:
            return place
        if self.county_name:
            return f"{self.county_name} (mjesto rada nije navedeno)"
        return "Mjesto rada nije navedeno"


class JobCardDTO(JobSummaryDTO):
    """A search result with the job page values a job card shows; None until the page is read or when it omits them.

    The text fields are as the page states them. conditions are the
    normalised ones stored with the page, None while details_status is not
    'fetched'; a None value within them is unknown.
    """

    workers_needed: int | None = None
    employment_type: str | None = None
    working_hours: str | None = None
    education: str | None = None
    experience: str | None = None
    accommodation: str | None = None
    conditions: JobConditionsDTO | None = None


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


class UnknownConditionsDTO(ModelConfigBaseModel):
    """Jobs the condition filters left out only because a value is unknown.

    Each such job matches every other criterion, and every condition filter
    either matches it or its value is unknown, so it could match if the
    unknown values were favourable. by_filter counts them per condition
    filter whose value is unknown, so a job unknown for two filters counts
    under both; total counts each job once and is 0 without condition filters.
    """

    by_filter: dict[str, int] = {}
    total: int = 0


class JobSearchPageDTO(ModelConfigBaseModel):
    """A search page.

    unknown_total and unknown_conditions are UnknownConditionsDTO's total
    and by_filter; they cover every page, not only this one.
    """

    jobs: tuple[JobSummaryDTO, ...]
    next_cursor: str | None
    coverage: CoverageDTO
    unknown_conditions: dict[str, int] = {}
    unknown_total: int = 0


class JobCardsPageDTO(ModelConfigBaseModel):
    """A search page of job cards; today is the day in Croatia that deadlines were compared with.

    unknown_conditions and unknown_total are as in JobSearchPageDTO.
    """

    jobs: tuple[JobCardDTO, ...]
    next_cursor: str | None
    coverage: CoverageDTO
    today: date
    unknown_conditions: dict[str, int] = {}
    unknown_total: int = 0


class ActiveFilterDTO(ModelConfigBaseModel):
    """A filter a view names in Croatian; argument is the tool argument that sets it."""

    argument: str
    label: str


class JobCardsDTO(JobCardsPageDTO):
    """A page of job cards for the job cards view, with its heading and the filters that found it.

    filters are the show_jobs arguments, so the view can ask for the next page
    with next_cursor. active_filters name the set filters but the query, which
    is in the title. coverage_note and unknown_note say in Croatian what
    coverage.warning and unknown_total do; each is None when there is nothing
    to say.
    """

    title: str
    description: str
    filters: JobSearchFiltersDTO
    active_filters: tuple[ActiveFilterDTO, ...]
    coverage_note: str | None
    unknown_note: str | None


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
    """Stored content of one job.

    description_text is the full text from the job page once it has been
    read; the feed's description is cut at 512 characters. The other page
    fields are None until then or when the page omits them.
    availability_status stays unknown until there is evidence the job is open
    or closed. Dropping out of every feed, or an HZZ error page, is not such
    evidence.
    """

    description_text: str | None
    description_source: Literal["job_page", "feed"] | None = None
    valid_from: date | None = None
    workers_needed: int | None = None
    employment_type: str | None = None
    working_hours: str | None = None
    work_schedule: str | None = None
    accommodation: str | None = None
    transport_allowance: str | None = None
    education: str | None = None
    experience: str | None = None
    details_checked_at: datetime | None = None
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
