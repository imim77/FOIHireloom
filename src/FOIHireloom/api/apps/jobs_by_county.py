"""Data for the jobs-by-county chart, which draws counties as 3D columns, by jobs or by workers sought.

The tool returns JobsByCountyDTO as structured content; the host loads the
views.JOBS_BY_COUNTY page in a sandboxed iframe and passes it that result
over the MCP Apps bridge. Text-only hosts still get the same data.
"""

from FOIHireloom.dto.job_market import (
    CountyMarketCountDTO,
    CountyMetric,
    CountyShareDTO,
    JobMarketFiltersDTO,
    JobMarketStatsDTO,
    JobsByCountyDTO,
)

from .labels import active_filters, coverage_note, filters_description, short_county_name, unknown_note

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
    counties = sorted(stats.counties, key=lambda county: (-getattr(county, metric), county.name))
    return JobsByCountyDTO(
        metric=metric,
        title=TITLES[metric],
        # The chart shows no chips, so its description names the filters.
        description=filters_description(filters, stats.today),
        today=stats.today,
        total_jobs=stats.jobs,
        total_workers_needed=stats.workers_needed,
        top=top,
        counties=tuple(_share(county, stats.jobs) for county in counties),
        coverage=stats.coverage,
        unknown_conditions=stats.unknown_conditions,
        unknown_total=stats.unknown_total,
        active_filters=active_filters(filters),
        coverage_note=coverage_note(stats.coverage),
        unknown_note=unknown_note(stats.unknown_conditions, stats.unknown_total),
    )


def _share(county: CountyMarketCountDTO, total_jobs: int) -> CountyShareDTO:
    return CountyShareDTO(
        code=county.code, name=county.name, short_name=short_county_name(county.name),
        jobs=county.jobs, workers_needed=county.workers_needed,
        share=round(100 * county.jobs / total_jobs, 1) if total_jobs else 0.0,
    )
