from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import ColumnElement, Subquery, Text, and_, func, not_, or_, select

from FOIHireloom.db.models import Job, JobFeedMembership, SourceFeed
from FOIHireloom.domain.search_text import SEARCH_FOLD_FROM, SEARCH_FOLD_TO
from FOIHireloom.dto.job_search import JobConditionFiltersDTO, JobFilterCriteriaDTO


def listed_condition(county_id: int | None = None) -> ColumnElement[bool]:
    """True for jobs present in a county feed, optionally of one county."""
    listed = (
        select(JobFeedMembership.job_id)
        .join(SourceFeed)
        .where(
            JobFeedMembership.job_id == Job.id,
            JobFeedMembership.presence_status == "present",
            SourceFeed.scope == "county",
        )
    )
    if county_id is not None:
        listed = listed.where(SourceFeed.county_id == county_id)
    return listed.exists()


def county_placements(*conditions: ColumnElement[bool]) -> Subquery:
    """Pairs of job_id and county_id for the county feeds matching conditions.

    A job listed by two feeds of one county appears once for that county.
    """
    return (
        select(JobFeedMembership.job_id, SourceFeed.county_id)
        .join(SourceFeed)
        .where(SourceFeed.scope == "county", *conditions)
        .distinct()
        .subquery()
    )


def terms_condition(terms: Sequence[str], weight: str = "") -> ColumnElement[bool]:
    """True when every term starts a word of the search document, or of its part with that weight."""
    query = " & ".join(f"{term}:*{weight}" for term in terms)
    return Job.search_vector.bool_op("@@")(func.to_tsquery("simple", query))


def filter_conditions(criteria: JobFilterCriteriaDTO) -> list[ColumnElement[bool]]:
    """Conditions for listed jobs matching every criterion, so search and statistics count the same jobs."""
    conditions = [listed_condition(criteria.county_id)]
    if criteria.terms:
        conditions.append(terms_condition(criteria.terms))
    if criteria.category is not None:
        conditions.append(func.upper(Job.category) == func.upper(criteria.category))
    if criteria.open_on is not None:
        conditions.append(open_condition(criteria.open_on))
    if criteria.skills:
        # An unmentioned skill does not count as an unknown working condition.
        conditions.append(Job.skills.overlap(list(criteria.skills)))
    return [*conditions, *condition_filters(criteria).values()]


def after_descending(keys: Sequence[tuple[ColumnElement, object]]) -> ColumnElement[bool]:
    """Rows after these descending keys, with NULL values last at each key."""
    equal = []
    later = []
    for column, value in keys:
        if value is not None:
            later.append(and_(*equal, or_(column < value, column.is_(None))))
        equal.append(column.is_not_distinct_from(value))
    return or_(*later)


@dataclass(frozen=True)
class ConditionFilter:
    """ConditionFilter matches jobs on one normalised condition and tells when a job's value is unknown.

    An unknown value is NULL and a comparison with NULL is never true, so a
    job for which unknown holds matches no value.
    """

    match: Callable[[Any], ColumnElement[bool]]
    unknown: ColumnElement[bool]


def _offers_accommodation(offered: bool) -> ColumnElement[bool]:
    offers = Job.accommodation != "none"
    return offers if offered else not_(offers)


def _works_in(place: str) -> ColumnElement[bool]:
    pattern = f"% {place} %"
    # The page names the county after a comma: "VARAŽDIN, VARAŽDINSKA ŽUPANIJA".
    return or_(place_words(func.split_part(Job.page_work_place, ",", 1)).like(pattern),
               place_words(Job.municipality).like(pattern))


# Condition filters by JobConditionFiltersDTO field; a new filter needs only
# an entry here for search, statistics and unknown-value counts to apply it.
CONDITION_FILTERS: dict[str, ConditionFilter] = {
    "max_experience_months": ConditionFilter(
        lambda months: Job.experience_months <= months, Job.experience_months.is_(None)),
    "contract": ConditionFilter(lambda contract: Job.contract == contract, Job.contract.is_(None)),
    "full_time": ConditionFilter(lambda full_time: Job.full_time == full_time, Job.full_time.is_(None)),
    "education": ConditionFilter(
        lambda education: Job.education_levels.contains([education]), Job.education_levels.is_(None)),
    "accommodation": ConditionFilter(_offers_accommodation, Job.accommodation.is_(None)),
    "employment_tags": ConditionFilter(
        lambda tags: Job.employment_tags.contains(list(tags)), Job.employment_tags.is_(None)),
    "place": ConditionFilter(_works_in, and_(Job.page_work_place.is_(None), Job.municipality.is_(None))),
}


def condition_filters(criteria: JobConditionFiltersDTO) -> dict[str, ColumnElement[bool]]:
    """Conditions for the condition filters that criteria sets, by filter name."""
    return {
        name: condition.match(value)
        for name, condition in CONDITION_FILTERS.items()
        if (value := getattr(criteria, name)) is not None
    }


def place_words(place: ColumnElement[str | None]) -> ColumnElement[str | None]:
    """The place's words folded as the search vector folds them, lowercase and each between spaces."""
    folded = func.lower(func.translate(place, SEARCH_FOLD_FROM, SEARCH_FOLD_TO))
    return " " + func.regexp_replace(folded, "[^[:alnum:]]+", " ", "g", type_=Text) + " "


def effective_deadline() -> ColumnElement[date]:
    """The closing date from the job page ("Natječaj vrijedi do"), else the feed's deadline."""
    return func.coalesce(Job.page_valid_until, Job.deadline_on)


def open_condition(open_on: date) -> ColumnElement[bool]:
    """True unless the job's known deadline is before open_on."""
    deadline = effective_deadline()
    return or_(deadline.is_(None), deadline >= open_on)


def page_due_condition(retry_before: datetime) -> ColumnElement[bool]:
    """True for jobs whose detail page was never fetched, is outdated, or may be retried."""
    return or_(
        Job.page_status == "pending",
        and_(Job.page_status == "fetched", Job.page_source_hash != Job.content_hash),
        and_(Job.page_status.in_(("unavailable", "failed")), Job.page_checked_at < retry_before),
    )
