from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, Text, and_, func, not_, or_, select

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


def condition_filters(criteria: JobConditionFiltersDTO) -> dict[str, ColumnElement[bool]]:
    """Conditions for the condition filters that criteria sets, by filter name.

    An unknown value is NULL and a comparison with NULL is never true, so a
    job whose value is unknown matches none of them.
    """
    conditions: dict[str, ColumnElement[bool]] = {}
    if criteria.max_experience_months is not None:
        conditions["max_experience_months"] = Job.experience_months <= criteria.max_experience_months
    if criteria.contract is not None:
        conditions["contract"] = Job.contract == criteria.contract
    if criteria.full_time is not None:
        conditions["full_time"] = Job.full_time == criteria.full_time
    if criteria.education is not None:
        conditions["education"] = Job.education_levels.contains([criteria.education])
    if criteria.accommodation is not None:
        offered = Job.accommodation != "none"
        conditions["accommodation"] = offered if criteria.accommodation else not_(offered)
    if criteria.employment_tags is not None:
        conditions["employment_tags"] = Job.employment_tags.contains(list(criteria.employment_tags))
    if criteria.place is not None:
        pattern = f"% {criteria.place} %"
        # The page names the county after a comma: "VARAŽDIN, VARAŽDINSKA ŽUPANIJA".
        conditions["place"] = or_(place_words(func.split_part(Job.page_work_place, ",", 1)).like(pattern),
                                  place_words(Job.municipality).like(pattern))
    return conditions


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
