from datetime import date
from typing import Literal

from .base import ModelConfigBaseModel
from .job_conditions import JobConditionsDTO, RawJobConditionsDTO
from .job_search import CandidateConditionsDTO, DetailsStatus, JobSummaryDTO

MIN_COMPARED_JOBS = 2
MAX_COMPARED_JOBS = 3

type ComparisonAspect = Literal["experience", "education", "contract", "working_time", "accommodation", "deadline"]
type ConditionVerdict = Literal["match", "no_match", "unknown"]
type UnknownReason = Literal[
    "page_not_read", "page_unavailable", "page_failed", "not_stated", "unreadable", "contract_not_stated",
]


class JobComparisonConditionsDTO(CandidateConditionsDTO):
    """The conditions a person states for a comparison, with the meanings of the filters of the same names.

    Each one set gets a verdict per job: "match" exactly when a search with
    that filter alone would find the job, "no_match" when the job's known
    value leaves it out, and "unknown" when its value is unknown.
    """


class ComparedJobDTO(ModelConfigBaseModel):
    """A compared job as its card names it; conditions are as in JobCardDTO, None while the page is not read.

    published_on, deadline_on and deadline_passed are as in JobSummaryDTO, so
    a view can word the deadline itself.
    """

    id: int
    display_title: str
    employer_name: str | None
    county_name: str | None
    display_location: str
    canonical_url: str
    details_status: DetailsStatus
    category: str | None
    category_source: Literal["description", "feed"] | None
    published_on: date | None
    deadline_on: date | None
    deadline_passed: bool | None = None
    conditions: JobConditionsDTO | None


class ComparisonCellDTO(ModelConfigBaseModel):
    """One job's value for one aspect of a comparison.

    value is a short English summary of the job's normalised value, None when
    it is unknown. evidence is the job page's own text for the aspect exactly
    as stored, None while the page is not read or when it does not state it;
    for the deadline it is the date and whether it came from the job page or
    the feed. verdict is None when the person set no condition for the aspect,
    and reason then is too; otherwise reason says in a short English sentence
    what in the job's data gave the verdict. unknown_reason is a code for why
    value is unknown, set whenever value is None on a condition aspect, with
    or without a verdict, and None otherwise, so also for the deadline.
    """

    job_id: int
    value: str | None
    evidence: str | None
    verdict: ConditionVerdict | None
    reason: str | None
    unknown_reason: UnknownReason | None = None


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


class ComparisonCellViewDTO(ComparisonCellDTO):
    """A cell with the Croatian wording the job comparison view shows.

    text is, for the deadline, "do 29. 11. 2026. (još 28 dana)", "do
    01. 11. 2026. (zadnji dan)", "istekao 31. 10. 2026." or "nije naveden";
    for the other aspects the job page's own text when it has one, else why
    the value is unknown (from unknown_reason, e.g. "oglas ne navodi"), else
    the known value in Croatian. note is why the value is unknown when text
    is the page's own text, e.g. "Novootvoreni poslovi" with "oglas navodi
    vrstu zaposlenja, ali ne i ugovor", None otherwise.
    verdict_label is the verdict in Croatian: "odgovara", "ne odgovara" or
    "nije poznato".
    """

    text: str
    note: str | None
    verdict_label: str | None


class ComparisonRowViewDTO(ComparisonRowDTO):
    """A row with its aspect's Croatian name and the person's condition in Croatian, None without one."""

    name: str
    condition_label: str | None
    cells: tuple[ComparisonCellViewDTO, ...]


class JobComparisonViewDTO(JobComparisonDTO):
    """A comparison for the job comparison view, with the Croatian wording it shows; the English fields stay.

    description names the person's conditions, or says there are none.
    disclaimer says a comparison shows only what the advertisements state;
    unknown_note says how many verdicts are unknown, None when none is.
    """

    title: str
    description: str
    disclaimer: str
    unknown_note: str | None
    rows: tuple[ComparisonRowViewDTO, ...]
