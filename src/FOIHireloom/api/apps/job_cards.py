"""Data for the job cards view, which shows each found job as a card.

The tool returns JobCardsDTO as structured content; the host loads the
views.JOB_CARDS page in a sandboxed iframe and passes it that result over
the MCP Apps bridge. Text-only hosts still get the same data.
"""

from FOIHireloom.dto.job_search import JobCardsDTO, JobCardsPageDTO, JobSearchFiltersDTO

DEFAULT_LIMIT = 6


def job_cards(page: JobCardsPageDTO, filters: JobSearchFiltersDTO) -> JobCardsDTO:
    query = (filters.query or "").strip()
    parts = [f"županija {filters.county.strip()}" if filters.county and filters.county.strip() else None,
             f"kategorija {filters.category.strip()}" if filters.category and filters.category.strip() else None,
             f"{'svi' if filters.include_expired else 'aktivni'} oglasi na dan {page.today:%d. %m. %Y.}"]
    description = " · ".join(part for part in parts if part)
    return JobCardsDTO(
        **page.model_dump(),
        title=f"Oglasi za „{query}”" if query else "Najnoviji oglasi",
        description=description[0].upper() + description[1:],
        # The next page continues from next_cursor; the view passes it back with these filters.
        filters=filters.model_copy(update={"cursor": None}),
    )
