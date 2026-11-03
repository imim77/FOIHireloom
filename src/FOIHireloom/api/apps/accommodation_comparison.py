"""The accommodation donut partitions exactly the ads returned by market_stats."""
from FOIHireloom.dto.accommodation_comparison import AccommodationComparisonDTO, AccommodationGroupDTO
from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO

from .labels import active_filters, coverage_note, day, sentence, unknown_note


def accommodation_comparison(stats: JobMarketStatsDTO, filters: JobMarketFiltersDTO) -> AccommodationComparisonDTO:
    # Filtering the dimension being compared would discard both other groups and bias the result.
    if filters.accommodation is not None:
        raise ValueError("Accommodation comparison must include all accommodation statuses")
    counts = {item.name: item.jobs for item in stats.accommodation}
    if set(counts) - {"none", "shared", "single", "family"}:
        raise ValueError("Unknown normalised accommodation type")
    known = sum(counts.values())
    if known > stats.jobs:
        raise ValueError("Accommodation counts exceed the matching job count")
    groups = (
        ("offered", "Nudi smještaj", sum(counts.get(key, 0) for key in ("shared", "single", "family"))),
        ("not_offered", "Bez smještaja", counts.get("none", 0)),
        ("unknown", "Podatak nije poznat", stats.jobs - known),
    )
    labels = active_filters(filters)
    query = (filters.query or "").strip()
    parts = [*([f"upit „{query}”"] if query else []),
             *(label.label for label in labels if label.argument != "include_expired"),
             day(stats.today, filters.include_expired)]
    notes = ["Broje se oglasi, a ne traženi radnici. Jedan oglas može tražiti više radnika.",
             "Nepoznat podatak ne znači da smještaj nije ponuđen. Kad su prikazane sve skupine, udjeli se odnose na sve odabrane oglase."]
    if query:
        notes.append("Upit pretražuje naslov i sadržaj oglasa; nije stroga klasifikacija zanimanja.")
    if (filters.category or "").strip():
        notes.append("Odabrana kategorija obuhvaća samo oglase kojima je kategorija poznata.")
    return AccommodationComparisonDTO(
        title="Smještaj u oglasima za posao", description=sentence(" · ".join(parts)), today=stats.today,
        total_jobs=stats.jobs, known_jobs=known,
        groups=tuple(AccommodationGroupDTO(key=key, label=label, jobs=count,
                                         share=round(100 * count / stats.jobs, 1) if stats.jobs else 0)
                     for key, label, count in groups),
        accommodation_types=stats.accommodation, coverage=stats.coverage, active_filters=labels,
        coverage_note=coverage_note(stats.coverage), unknown_conditions=stats.unknown_conditions,
        unknown_total=stats.unknown_total, unknown_note=unknown_note(stats.unknown_conditions, stats.unknown_total),
        view_notes=tuple(notes),
    )
