from datetime import date
from typing import Literal

from .base import ModelConfigBaseModel
from .job_conditions import JobConditionsDTO, RawJobConditionsDTO
from .job_search import CandidateConditionsDTO, DetailsStatus, JobSummaryDTO

MIN_COMPARED_JOBS = 2
MAX_COMPARED_JOBS = 3

# The aspects a comparison shows, in its order.
type ComparisonAspect = Literal["experience", "education", "contract", "working_time", "accommodation", "deadline"]
# match: the job's own value meets the person's condition; no_match: it is known and does not; unknown: the job's
# value is not known. A verdict is about what the job page states, never about whether the employer would accept
# the person.
type ConditionVerdict = Literal["match", "no_match", "unknown"]


class JobComparisonConditionsDTO(CandidateConditionsDTO):
    """The conditions a person states for a comparison, with the meanings of the filters of the same names.

    Each one set gets a verdict per job: "match" exactly when a search with
    that filter alone would find the job, "no_match" when the job's known
    value leaves it out, and "unknown" when its value is unknown.
    """


class ComparedJobDTO(ModelConfigBaseModel):
    """A compared job as its card names it; conditions are as in JobCardDTO, None while the page is not read."""

    id: int
    display_title: str
    employer_name: str | None
    county_name: str | None
    display_location: str
    canonical_url: str
    details_status: DetailsStatus
    category: str | None
    category_source: Literal["description", "feed"] | None
    conditions: JobConditionsDTO | None


class ComparisonCellDTO(ModelConfigBaseModel):
    """One job's value for one aspect of a comparison.

    value is a short English summary of the job's normalised value, None when
    it is unknown. evidence is the job page's own text for the aspect exactly
    as stored, None while the page is not read or when it does not state it;
    for the deadline it is the date and whether it came from the job page or
    the feed. verdict is None when the person set no condition for the aspect,
    and reason then is too; otherwise reason says in a short English sentence
    what in the job's data gave the verdict.
    """

    job_id: int
    value: str | None
    evidence: str | None
    verdict: ConditionVerdict | None
    reason: str | None


class ComparisonRowDTO(ModelConfigBaseModel):
    """One aspect across the compared jobs, with a cell per job in the jobs' order.

    condition is the person's value for the aspect (max_experience_months,
    education, contract, full_time or accommodation), None without one; the
    deadline has none. differs is True when the cells' values are not all
    equal: an unknown value differs from a known one, two unknown ones do not.
    """

    aspect: ComparisonAspect
    differs: bool
    condition: bool | int | str | None
    cells: tuple[ComparisonCellDTO, ...]


class JobComparisonDTO(ModelConfigBaseModel):
    """Two or three jobs side by side, in the requested order.

    today is the day in Croatia the deadlines were compared with. rows hold
    the aspects in the order experience, education, contract, working_time,
    accommodation and deadline. conditions are the person's conditions, None
    when none is set.
    """

    today: date
    jobs: tuple[ComparedJobDTO, ...]
    rows: tuple[ComparisonRowDTO, ...]
    conditions: JobComparisonConditionsDTO | None


class JobComparisonInputDTO(ModelConfigBaseModel):
    """What a comparison reads about one job: its summary, stored conditions and job page text.

    conditions and page are None while the page is not read, as in JobCardDTO.
    """

    summary: JobSummaryDTO
    conditions: JobConditionsDTO | None
    page: RawJobConditionsDTO | None
