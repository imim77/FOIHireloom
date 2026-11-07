"""The accommodation donut partitions exactly the ads returned by market_stats."""
from FOIHireloom.dto.accommodation_comparison import AccommodationComparisonDTO, AccommodationGroupDTO
from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO

from .labels import active_filters, coverage_note, filters_description, unknown_note

TITLE = "Smještaj u oglasima za posao"
OFFERED = ("shared", "single", "family")
NOTES = ("Broje se oglasi, a ne traženi radnici. Jedan oglas može tražiti više radnika.",
         "Nepoznat podatak ne znači da smještaj nije ponuđen. Kad su prikazane sve skupine, udjeli se odnose na sve "
         "odabrane oglase.")
NOTE_QUERY = "Upit pretražuje naslov i sadržaj oglasa; nije stroga klasifikacija zanimanja."
NOTE_CATEGORY = "Odabrana kategorija obuhvaća samo oglase kojima je kategorija poznata."


def accommodation_comparison(stats: JobMarketStatsDTO, filters: JobMarketFiltersDTO) -> AccommodationComparisonDTO:
    # Filtering the dimension being compared would discard both other groups and bias the result.
    if filters.accommodation is not None:
        raise ValueError("Accommodation comparison must include all accommodation statuses")
    counts = _known_counts(stats)
    return AccommodationComparisonDTO(
        title=TITLE, description=filters_description(filters, stats.today), today=stats.today,
        total_jobs=stats.jobs, known_jobs=sum(counts.values()), groups=_groups(counts, stats.jobs),
        accommodation_types=stats.accommodation, coverage=stats.coverage, active_filters=active_filters(filters),
        coverage_note=coverage_note(stats.coverage), unknown_conditions=stats.unknown_conditions,
        unknown_total=stats.unknown_total, unknown_note=unknown_note(stats.unknown_conditions, stats.unknown_total),
        view_notes=_notes(filters),
    )


def _known_counts(stats: JobMarketStatsDTO) -> dict[str, int]:
    """Ads by normalised accommodation type, checked to be part of the matching ads."""
    counts = {item.name: item.jobs for item in stats.accommodation}
    if set(counts) - {"none", *OFFERED}:
        raise ValueError("Unknown normalised accommodation type")
    if sum(counts.values()) > stats.jobs:
        raise ValueError("Accommodation counts exceed the matching job count")
    return counts


def _groups(counts: dict[str, int], total: int) -> tuple[AccommodationGroupDTO, ...]:
    groups = (
        ("offered", "Nudi smještaj", sum(counts.get(key, 0) for key in OFFERED)),
        ("not_offered", "Bez smještaja", counts.get("none", 0)),
        ("unknown", "Podatak nije poznat", total - sum(counts.values())),
    )
    return tuple(AccommodationGroupDTO(key=key, label=label, jobs=count,
                                       share=round(100 * count / total, 1) if total else 0)
                 for key, label, count in groups)


def _notes(filters: JobMarketFiltersDTO) -> tuple[str, ...]:
    return (*NOTES, *([NOTE_QUERY] if (filters.query or "").strip() else []),
            *([NOTE_CATEGORY] if (filters.category or "").strip() else []))
