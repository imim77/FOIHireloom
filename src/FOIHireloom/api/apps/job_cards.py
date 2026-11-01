"""Data for the job cards view, which shows each found job as a card.

The tool returns JobCardsDTO as structured content; the host loads the
views.JOB_CARDS page in a sandboxed iframe and passes it that result over
the MCP Apps bridge. Text-only hosts still get the same data.
"""

from FOIHireloom.dto.job_search import JobCardsDTO, JobCardsPageDTO, JobSearchFiltersDTO

from .labels import active_filters, coverage_note, day, sentence, unknown_note

DEFAULT_LIMIT = 6


def job_cards(page: JobCardsPageDTO, filters: JobSearchFiltersDTO) -> JobCardsDTO:
    query = (filters.query or "").strip()
    return JobCardsDTO(
        **page.model_dump(),
        title=f"Oglasi za „{query}”" if query else "Najnoviji oglasi",
        # The view shows the filters as chips under it.
        description=sentence(day(page.today, filters.include_expired)),
        # The next page continues from next_cursor; the view passes it back with these filters.
        filters=filters.model_copy(update={"cursor": None}),
        active_filters=active_filters(filters),
        coverage_note=coverage_note(page.coverage),
        unknown_note=unknown_note(page.unknown_conditions, page.unknown_total),
    )
