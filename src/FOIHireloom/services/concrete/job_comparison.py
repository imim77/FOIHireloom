from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, get_args

from FOIHireloom.dto.job_comparison import (
    ComparisonAspect,
    ComparisonCellDTO,
    ComparisonRowDTO,
    ConditionVerdict,
    JobComparisonInputDTO,
    UnknownReason,
)
from FOIHireloom.dto.job_conditions import EducationLevel, JobConditionsDTO
from FOIHireloom.dto.job_search import CandidateConditionsDTO


@dataclass(frozen=True)
class ConditionRule:
    """ConditionRule decides one person's condition on a job the way the search filter of the same name does.

    name is the CandidateConditionsDTO field, job_value reads the job's
    value and meets tells whether a known job value meets the person's.
    """

    name: str
    job_value: Callable[[JobConditionsDTO], Any]
    meets: Callable[[Any, Any], bool]


CONDITION_RULES: dict[str, ConditionRule] = {rule.name: rule for rule in (
    ConditionRule("max_experience_months", lambda conditions: conditions.experience_months,
                  lambda months, most: months <= most),
    ConditionRule("education", lambda conditions: conditions.education_levels, lambda levels, level: level in levels),
    ConditionRule("contract", lambda conditions: conditions.contract, lambda contract, wanted: contract == wanted),
    ConditionRule("full_time", lambda conditions: conditions.full_time, lambda full_time, wanted: full_time == wanted),
    ConditionRule("accommodation", lambda conditions: conditions.accommodation,
                  lambda accommodation, wanted: (accommodation != "none") == wanted),
)}

EDUCATION_ORDER: tuple[str, ...] = get_args(EducationLevel.__value__)
EDUCATION_NAMES = {
    "primary_lower": "lower primary grades",
    "primary": "primary school",
    "secondary_3": "secondary school (3 years)",
    "secondary_4": "secondary school (4 years)",
    "college": "college or bachelor's degree",
    "university": "university degree",
}
CONTRACT_NAMES = {"permanent": "permanent", "fixed_term": "fixed term", "other": "another form of work"}
ACCOMMODATION_NAMES = {
    "none": "no accommodation",
    "shared": "shared accommodation",
    "single": "single accommodation",
    "family": "a family flat",
}
# Why every condition of a job is unknown while its page is not read, by its details_status.
UNREAD_REASONS = {
    "pending": "the job's HZZ page has not been read yet",
    "unavailable": "HZZ did not return the job's page, so its conditions are unknown",
    "failed": "reading the job's HZZ page failed, so its conditions are unknown",
    "fetched": "the job's conditions are unknown",
}
# The unknown_reason code of every condition of a job whose page is not read, by its details_status. A fetched job
# without stored conditions has not had its page read either.
UNREAD_CODES: dict[str, UnknownReason] = {
    "pending": "page_not_read",
    "unavailable": "page_unavailable",
    "failed": "page_failed",
    "fetched": "page_not_read",
}


class JobConditionMatcher:
    """Decide whether a job's normalised conditions meet a person's conditions, as the search filters do.

    A verdict is "match" exactly when a search with that condition alone as
    its filter finds the job, "no_match" when the job's known value leaves it
    out, and "unknown" when the value is unknown, so also for every
    condition while the job page is not read (conditions None).
    """

    def verdicts(
        self, conditions: JobConditionsDTO | None, wanted: CandidateConditionsDTO,
    ) -> dict[str, ConditionVerdict]:
        """A verdict for each condition wanted sets, by its name."""
        known = conditions or JobConditionsDTO()
        return {name: self._verdict(CONDITION_RULES[name], known, value)
                for name, value in wanted.model_dump(include=set(CONDITION_RULES), exclude_none=True).items()}

    @staticmethod
    def _verdict(rule: ConditionRule, conditions: JobConditionsDTO, wanted: Any) -> ConditionVerdict:
        job_value = rule.job_value(conditions)
        if job_value is None:
            return "unknown"
        return "match" if rule.meets(job_value, wanted) else "no_match"


class ComparisonAspectRow(ABC):
    """ComparisonAspectRow writes one aspect's cell for each compared job.

    A new aspect is a new subclass listed in ASPECT_ROWS. condition names
    the CandidateConditionsDTO field whose verdict the cells explain, or is
    None for an aspect no condition is set on.
    """

    aspect: ComparisonAspect
    condition: str | None = None

    @abstractmethod
    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        """Return the job's cell; verdict is None when the person did not set this aspect's condition."""


class ConditionAspectRow(ComparisonAspectRow, ABC):
    """ConditionAspectRow writes the cell of an aspect read from the job page, explaining unknown values."""

    @staticmethod
    def _cell(job: JobComparisonInputDTO, value: str | None, evidence: str | None, verdict: ConditionVerdict | None,
              reasons: Callable[[ConditionVerdict], str], unknown: Callable[[], UnknownReason]) -> ComparisonCellDTO:
        return ComparisonCellDTO(job_id=job.summary.id, value=value, evidence=evidence, verdict=verdict,
                                 reason=None if verdict is None else reasons(verdict),
                                 unknown_reason=unknown() if value is None else None)

    @staticmethod
    def _unknown_code(job: JobComparisonInputDTO, field: str) -> UnknownReason:
        """Why the job's value from the page field is unknown, as an unknown_reason code; see _unknown."""
        if job.conditions is None:
            return UNREAD_CODES[job.summary.details_status]
        return "unreadable" if field in job.conditions.unrecognised else "not_stated"

    @staticmethod
    def _unknown(job: JobComparisonInputDTO, field: str, subject: str) -> str:
        """Why the job's value from the page field is unknown."""
        if job.conditions is None:
            return UNREAD_REASONS[job.summary.details_status]
        if field in job.conditions.unrecognised:
            return f"the job page states the {subject} in a way that could not be read"
        return f"the job page does not state the {subject}"

    @staticmethod
    def _evidence(job: JobComparisonInputDTO, field: str) -> str | None:
        return None if job.page is None else getattr(job.page, field)


class ExperienceRow(ConditionAspectRow):
    aspect = "experience"
    condition = "max_experience_months"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        known = job.conditions or JobConditionsDTO()
        months, have = known.experience_months, wanted.max_experience_months
        if months is None:
            value = None
        elif known.trainee:
            value = "trainee ad"
        elif months == 0:
            value = "no experience required"
        else:
            value = _months(months)

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "experience", "experience")
            if months == 0:
                return "the job is a trainee ad, which asks for no experience" if known.trainee else \
                    "the job asks for no experience"
            return f"the job asks for {_months(months)} of experience; you have {_months(have) if have else 'none'}"

        return self._cell(job, value, self._evidence(job, "experience"), verdict, reasons,
                          lambda: self._unknown_code(job, "experience"))


class EducationRow(ConditionAspectRow):
    aspect = "education"
    condition = "education"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        levels = (job.conditions or JobConditionsDTO()).education_levels
        value = None if levels is None else _levels(levels)
        level = wanted.education

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "education", "education")
            if verdict == "match":
                return f"the job page lists {EDUCATION_NAMES[level]} among the accepted levels"
            return f"the job page asks for {value}, not {EDUCATION_NAMES[level]}"

        return self._cell(job, value, self._evidence(job, "education"), verdict, reasons,
                          lambda: self._unknown_code(job, "education"))


class ContractRow(ConditionAspectRow):
    aspect = "contract"
    condition = "contract"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        conditions = job.conditions
        contract = None if conditions is None else conditions.contract
        value = None if contract is None else CONTRACT_NAMES[contract]
        evidence = self._evidence(job, "employment_type")
        # The page states a type of employment it recognised, but no contract among it.
        types_only = conditions is not None and bool(evidence) and "employment_type" not in conditions.unrecognised

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "match":
                return f"the job's contract is {value}, as you want"
            if verdict == "no_match":
                return f"the job's contract is {value}; you want {CONTRACT_NAMES[wanted.contract]}"
            if types_only:
                return "the job page states the type of employment but not the contract"
            return self._unknown(job, "employment_type", "contract")

        def unknown() -> UnknownReason:
            return "contract_not_stated" if types_only else self._unknown_code(job, "employment_type")

        return self._cell(job, value, evidence, verdict, reasons, unknown)


class WorkingTimeRow(ConditionAspectRow):
    aspect = "working_time"
    condition = "full_time"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        known = job.conditions or JobConditionsDTO()
        full_time, hours = known.full_time, known.weekly_hours
        kind = None if full_time is None else "full time" if full_time else "part time"
        value = None if kind is None else kind if hours is None else f"{kind}, {hours} h a week"

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "working_hours", "working time")
            stated = kind if hours is None else f"{kind} ({hours} h a week)"
            if verdict == "match":
                return f"the job is {stated}, as you want"
            return f"the job is {stated}; you want {'full time' if wanted.full_time else 'part time'}"

        return self._cell(job, value, self._evidence(job, "working_hours"), verdict, reasons,
                          lambda: self._unknown_code(job, "working_hours"))


class AccommodationRow(ConditionAspectRow):
    aspect = "accommodation"
    condition = "accommodation"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        accommodation = (job.conditions or JobConditionsDTO()).accommodation
        value = None if accommodation is None else ACCOMMODATION_NAMES[accommodation]

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "accommodation", "accommodation")
            if wanted.accommodation:
                return f"the job offers {value}" if verdict == "match" else \
                    "the job offers no accommodation; you want some"
            return "the job offers no accommodation, as you want" if verdict == "match" else \
                f"the job offers {value}; you want a job without accommodation"

        return self._cell(job, value, self._evidence(job, "accommodation"), verdict, reasons,
                          lambda: self._unknown_code(job, "accommodation"))


class DeadlineRow(ComparisonAspectRow):
    aspect = "deadline"

    def cell(self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: CandidateConditionsDTO,
             today: date) -> ComparisonCellDTO:
        deadline, source = job.summary.deadline_on, job.summary.deadline_source
        if deadline is None:
            value = evidence = None
        else:
            value = _time_left(deadline, today)
            evidence = f"{deadline.isoformat()}, from the {'job page' if source == 'job_page' else 'HZZ feed'}"
        return ComparisonCellDTO(job_id=job.summary.id, value=value, evidence=evidence, verdict=None, reason=None)


# The comparison's rows, in order.
ASPECT_ROWS: tuple[ComparisonAspectRow, ...] = (
    ExperienceRow(), EducationRow(), ContractRow(), WorkingTimeRow(), AccommodationRow(), DeadlineRow(),
)


class JobComparator:
    """Lay out two or three jobs aspect by aspect, with a verdict for each condition the person set.

    Values and reasons are short English text made from the job's stored
    data only; nothing unknown is filled in, and a verdict says whether the
    job's stated condition meets the person's, never whether the employer
    would accept them.
    """

    def __init__(self, matcher: JobConditionMatcher) -> None:
        self._matcher = matcher

    def rows(
        self, jobs: Sequence[JobComparisonInputDTO], today: date, wanted: CandidateConditionsDTO | None,
    ) -> tuple[ComparisonRowDTO, ...]:
        wanted = wanted or CandidateConditionsDTO()
        verdicts = [self._matcher.verdicts(job.conditions, wanted) for job in jobs]
        return tuple(self._row(row, jobs, verdicts, wanted, today) for row in ASPECT_ROWS)

    @staticmethod
    def _row(row: ComparisonAspectRow, jobs: Sequence[JobComparisonInputDTO],
             verdicts: Sequence[dict[str, ConditionVerdict]], wanted: CandidateConditionsDTO,
             today: date) -> ComparisonRowDTO:
        condition = row.condition
        cells = tuple(row.cell(job, None if condition is None else job_verdicts.get(condition), wanted, today)
                      for job, job_verdicts in zip(jobs, verdicts))
        return ComparisonRowDTO(aspect=row.aspect, differs=len({cell.value for cell in cells}) > 1,
                                condition=None if condition is None else getattr(wanted, condition), cells=cells)


def _time_left(deadline: date, today: date) -> str:
    days = (deadline - today).days
    if days < 0:
        return f"expired on {deadline.isoformat()}"
    left = "last day" if days == 0 else "1 day left" if days == 1 else f"{days} days left"
    return f"open until {deadline.isoformat()} ({left})"


def _months(months: int) -> str:
    return "1 month" if months == 1 else f"{months} months"


def _levels(levels: Sequence[str]) -> str:
    """The accepted levels, or the lowest one "or higher levels" when every higher level is accepted too."""
    names = [EDUCATION_NAMES[level] for level in levels]
    if len(levels) > 1 and tuple(levels) == EDUCATION_ORDER[-len(levels):]:
        return f"{names[0]} or higher levels"
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
