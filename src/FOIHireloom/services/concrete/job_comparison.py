from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, get_args

from FOIHireloom.dto.job_comparison import (
    ComparisonAspect,
    ComparisonCellDTO,
    ComparisonRowDTO,
    ConditionVerdict,
    JobComparisonInputDTO,
)
from FOIHireloom.dto.job_conditions import EducationLevel, JobConditionsDTO
from FOIHireloom.dto.job_search import CandidateConditionsDTO

# The aspect each person's condition is compared on, in the comparison's order.
CONDITION_ASPECTS: dict[str, ComparisonAspect] = {
    "max_experience_months": "experience",
    "education": "education",
    "contract": "contract",
    "full_time": "working_time",
    "accommodation": "accommodation",
}
# The JobConditionsDTO value each condition is decided on.
CONDITION_VALUES: dict[str, Callable[[JobConditionsDTO], Any]] = {
    "max_experience_months": lambda conditions: conditions.experience_months,
    "education": lambda conditions: conditions.education_levels,
    "contract": lambda conditions: conditions.contract,
    "full_time": lambda conditions: conditions.full_time,
    "accommodation": lambda conditions: conditions.accommodation,
}
# Whether a known job value meets the person's value, as the search filter of the same name decides.
CONDITION_TESTS: dict[str, Callable[[Any, Any], bool]] = {
    "max_experience_months": lambda months, most: months <= most,
    "education": lambda levels, level: level in levels,
    "contract": lambda contract, wanted: contract == wanted,
    "full_time": lambda full_time, wanted: full_time == wanted,
    "accommodation": lambda accommodation, wanted: (accommodation != "none") == wanted,
}
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
        verdicts: dict[str, ConditionVerdict] = {}
        for name, value in wanted.model_dump(include=set(CONDITION_TESTS), exclude_none=True).items():
            job_value = CONDITION_VALUES[name](known)
            if job_value is None:
                verdicts[name] = "unknown"
            else:
                verdicts[name] = "match" if CONDITION_TESTS[name](job_value, value) else "no_match"
        return verdicts


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
        cells: dict[ComparisonAspect, Callable[[JobComparisonInputDTO, ConditionVerdict | None], ComparisonCellDTO]]
        cells = {
            "experience": lambda job, verdict: self._experience(job, verdict, wanted.max_experience_months),
            "education": lambda job, verdict: self._education(job, verdict, wanted.education),
            "contract": lambda job, verdict: self._contract(job, verdict, wanted.contract),
            "working_time": lambda job, verdict: self._working_time(job, verdict, wanted.full_time),
            "accommodation": lambda job, verdict: self._accommodation(job, verdict, wanted.accommodation),
            "deadline": lambda job, _: self._deadline(job, today),
        }
        names = {aspect: name for name, aspect in CONDITION_ASPECTS.items()}
        rows = []
        for aspect, cell in cells.items():
            name = names.get(aspect)
            row = tuple(cell(job, None if name is None else job_verdicts.get(name))
                        for job, job_verdicts in zip(jobs, verdicts))
            rows.append(ComparisonRowDTO(aspect=aspect, differs=len({item.value for item in row}) > 1,
                                         condition=None if name is None else getattr(wanted, name), cells=row))
        return tuple(rows)

    @staticmethod
    def _cell(job: JobComparisonInputDTO, value: str | None, evidence: str | None, verdict: ConditionVerdict | None,
              reasons: Callable[[ConditionVerdict], str]) -> ComparisonCellDTO:
        return ComparisonCellDTO(job_id=job.summary.id, value=value, evidence=evidence, verdict=verdict,
                                 reason=None if verdict is None else reasons(verdict))

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

    def _experience(
        self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, have: int | None,
    ) -> ComparisonCellDTO:
        known = job.conditions or JobConditionsDTO()
        months = known.experience_months
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

        return self._cell(job, value, self._evidence(job, "experience"), verdict, reasons)

    def _education(
        self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, level: str | None,
    ) -> ComparisonCellDTO:
        levels = (job.conditions or JobConditionsDTO()).education_levels
        value = None if levels is None else _levels(levels)

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "education", "education")
            if verdict == "match":
                return f"the job page lists {EDUCATION_NAMES[level]} among the accepted levels"
            return f"the job page asks for {value}, not {EDUCATION_NAMES[level]}"

        return self._cell(job, value, self._evidence(job, "education"), verdict, reasons)

    def _contract(
        self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: str | None,
    ) -> ComparisonCellDTO:
        conditions = job.conditions
        contract = None if conditions is None else conditions.contract
        value = None if contract is None else CONTRACT_NAMES[contract]
        evidence = self._evidence(job, "employment_type")

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "match":
                return f"the job's contract is {value}, as you want"
            if verdict == "no_match":
                return f"the job's contract is {value}; you want {CONTRACT_NAMES[wanted]}"
            if conditions is not None and evidence and "employment_type" not in conditions.unrecognised:
                return "the job page states the type of employment but not the contract"
            return self._unknown(job, "employment_type", "contract")

        return self._cell(job, value, evidence, verdict, reasons)

    def _working_time(
        self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: bool | None,
    ) -> ComparisonCellDTO:
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
            return f"the job is {stated}; you want {'full time' if wanted else 'part time'}"

        return self._cell(job, value, self._evidence(job, "working_hours"), verdict, reasons)

    def _accommodation(
        self, job: JobComparisonInputDTO, verdict: ConditionVerdict | None, wanted: bool | None,
    ) -> ComparisonCellDTO:
        accommodation = (job.conditions or JobConditionsDTO()).accommodation
        value = None if accommodation is None else ACCOMMODATION_NAMES[accommodation]

        def reasons(verdict: ConditionVerdict) -> str:
            if verdict == "unknown":
                return self._unknown(job, "accommodation", "accommodation")
            if wanted:
                return f"the job offers {value}" if verdict == "match" else \
                    "the job offers no accommodation; you want some"
            return "the job offers no accommodation, as you want" if verdict == "match" else \
                f"the job offers {value}; you want a job without accommodation"

        return self._cell(job, value, self._evidence(job, "accommodation"), verdict, reasons)

    @staticmethod
    def _deadline(job: JobComparisonInputDTO, today: date) -> ComparisonCellDTO:
        deadline, source = job.summary.deadline_on, job.summary.deadline_source
        if deadline is None:
            value = evidence = None
        else:
            days = (deadline - today).days
            if days < 0:
                value = f"expired on {deadline.isoformat()}"
            else:
                left = "last day" if days == 0 else "1 day left" if days == 1 else f"{days} days left"
                value = f"open until {deadline.isoformat()} ({left})"
            evidence = f"{deadline.isoformat()}, from the {'job page' if source == 'job_page' else 'HZZ feed'}"
        return ComparisonCellDTO(job_id=job.summary.id, value=value, evidence=evidence, verdict=None, reason=None)


def _months(months: int) -> str:
    return "1 month" if months == 1 else f"{months} months"


def _levels(levels: Sequence[str]) -> str:
    """The accepted levels, or the lowest one "or higher levels" when every higher level is accepted too."""
    names = [EDUCATION_NAMES[level] for level in levels]
    if len(levels) > 1 and tuple(levels) == EDUCATION_ORDER[-len(levels):]:
        return f"{names[0]} or higher levels"
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
