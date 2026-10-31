"""Data for the jobs-by-county chart, which draws counties as 3D columns, by jobs or by workers sought.

The tool returns JobsByCountyDTO as structured content; the host loads the
views.JOBS_BY_COUNTY page in a sandboxed iframe and passes it that result
over the MCP Apps bridge. Text-only hosts still get the same data.
"""

from FOIHireloom.dto.job_market import CountyMetric, CountyShareDTO, JobMarketStatsDTO, JobsByCountyDTO

DEFAULT_TOP = 7
# There are 21 counties.
MAX_TOP = 21
TITLES: dict[CountyMetric, str] = {
    "jobs": "Broj oglasa po županijama",
    "workers_needed": "Broj traženih radnika po županijama",
}


def jobs_by_county(
    stats: JobMarketStatsDTO, top: int, query: str | None, category: str | None, metric: CountyMetric = "jobs",
) -> JobsByCountyDTO:
    filters = [f"upit „{query.strip()}”" if query and query.strip() else None,
               f"kategorija {category.strip()}" if category and category.strip() else None]
    description = " · ".join([*(f for f in filters if f), f"aktivni oglasi na dan {stats.today:%d. %m. %Y.}"])
    counties = sorted(stats.counties, key=lambda county: (-getattr(county, metric), county.name))
    return JobsByCountyDTO(
        metric=metric,
        title=TITLES[metric],
        description=description[0].upper() + description[1:],
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
    )
