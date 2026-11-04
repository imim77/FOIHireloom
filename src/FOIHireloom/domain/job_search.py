import base64
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from FOIHireloom.dto.job_search import SEARCH_TERM, JobConditionFiltersDTO, JobCursorDTO, JobSummaryDTO
from FOIHireloom.exceptions import InvalidJobSearchError

from .croatian_stem import stem
from .search_text import SEARCH_FOLD

# HZZ deadlines are Croatian calendar days and stay open until the end of the day.
LOCAL_TIME_ZONE = ZoneInfo("Europe/Zagreb")
INVALID_CURSOR = "The cursor is not valid; start the search again without it."


class JobCursorCodec:
    """JobCursorCodec preserves the search order when continuing a page."""

    @staticmethod
    def encode(job: JobSummaryDTO) -> str:
        cursor = JobCursorDTO(title_match=job.title_match, published_on=job.published_on, id=job.id)
        return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode()

    @staticmethod
    def decode(cursor: str) -> JobCursorDTO:
        try:
            return JobCursorDTO.model_validate_json(base64.urlsafe_b64decode(cursor.encode("ascii")))
        except (ValueError, ValidationError) as error:
            raise InvalidJobSearchError(INVALID_CURSOR) from error


def local_date(moment: datetime) -> date:
    """The day in Croatia at moment; HZZ deadlines are Croatian calendar days."""
    return moment.astimezone(LOCAL_TIME_ZONE).date()


def search_terms(query: str | None) -> tuple[str, ...]:
    """The query's words, folded and stemmed as the search vector is; raise InvalidJobSearchError without any."""
    if query is None or not query.strip():
        return ()
    # Stemmed, so "medicinske sestre" also finds "MEDICINSKA SESTRA".
    words = SEARCH_TERM.findall(query.translate(SEARCH_FOLD).casefold())
    terms = tuple(dict.fromkeys(stem(word) for word in words))
    if not terms:
        raise InvalidJobSearchError("The query contains no searchable words.")
    return terms


def condition_criteria(filters: JobConditionFiltersDTO) -> dict[str, object]:
    """The condition filters as criteria; no employment tags or a blank place is no filter."""
    place = None
    if filters.place and filters.place.strip():
        # Folded as query words are, but not stemmed: a place name matches as whole words.
        if not (words := SEARCH_TERM.findall(filters.place.translate(SEARCH_FOLD).casefold())):
            raise InvalidJobSearchError("The place contains no words.")
        place = " ".join(words)
    return filters.model_dump(include=set(JobConditionFiltersDTO.model_fields)) | {
        "employment_tags": filters.employment_tags or None, "place": place,
    }
