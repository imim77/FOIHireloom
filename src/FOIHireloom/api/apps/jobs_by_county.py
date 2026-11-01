"""Data for the jobs-by-county chart, which draws counties as 3D columns, by jobs or by workers sought.

The tool returns JobsByCountyDTO as structured content; the host loads the
views.JOBS_BY_COUNTY page in a sandboxed iframe and passes it that result
over the MCP Apps bridge. Text-only hosts still get the same data.
"""

from FOIHireloom.dto.job_market import (
    CountyMetric,
    CountyShareDTO,
    JobMarketFiltersDTO,
    JobMarketStatsDTO,
    JobsByCountyDTO,
)

from .labels import active_filters, coverage_note, day, sentence, unknown_note

DEFAULT_TOP = 7
# There are 21 counties.
MAX_TOP = 21
TITLES: dict[CountyMetric, str] = {
    "jobs": "Broj oglasa po županijama",
    "workers_needed": "Broj traženih radnika po županijama",
}


def jobs_by_county(
    stats: JobMarketStatsDTO, top: int, filters: JobMarketFiltersDTO, metric: CountyMetric = "jobs",
) -> JobsByCountyDTO:
    query = (filters.query or "").strip()
    labels = active_filters(filters)
    # The chart shows no chips, so its description names the filters; the day says whether expired jobs count.
    parts = [*([f"upit „{query}”"] if query else []),
             *(label.label for label in labels if label.argument != "include_expired"),
             day(stats.today, filters.include_expired)]
    counties = sorted(stats.counties, key=lambda county: (-getattr(county, metric), county.name))
    return JobsByCountyDTO(
        metric=metric,
        title=TITLES[metric],
        description=sentence(" · ".join(parts)),
        today=stats.today,
        total_jobs=stats.jobs,
        total_workers_needed=stats.workers_needed,
        top=top,
        counties=tuple(
            CountyShareDTO(
                code=county.code, name=county.name, short_name=county.name.removesuffix(" županija"),
                jobs=county.jobs, workers_needed=county.workers_needed,
                share=round(100 * county.jobs / stats.jobs, 1) if stats.jobs else 0.0,
            )
            for county in counties
        ),
        coverage=stats.coverage,
        unknown_conditions=stats.unknown_conditions,
        unknown_total=stats.unknown_total,
        active_filters=labels,
        coverage_note=coverage_note(stats.coverage),
        unknown_note=unknown_note(stats.unknown_conditions, stats.unknown_total),
    )
