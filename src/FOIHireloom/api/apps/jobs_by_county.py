"""The jobs-by-county chart: a ui:// page that draws the counties with the most jobs as 3D columns.

The tool returns JobsByCountyDTO as structured content; the host loads the
page in a sandboxed iframe and passes it that result over the MCP Apps
bridge. Text-only hosts still get the same data.
"""

from importlib.resources import files

from FOIHireloom.dto.job_market import CountyShareDTO, JobMarketStatsDTO, JobsByCountyDTO

RESOURCE_URI = "ui://foihireloom/jobs-by-county.html"
# The page loads the MCP Apps SDK from this origin, so its CSP must allow it.
SDK_ORIGIN = "https://unpkg.com"
DEFAULT_TOP = 8
# There are 21 counties.
MAX_TOP = 21


def page() -> str:
    return files(__package__).joinpath("jobs_by_county.html").read_text(encoding="utf-8")


def jobs_by_county(stats: JobMarketStatsDTO, top: int, query: str | None, category: str | None) -> JobsByCountyDTO:
    filters = [f"upit „{query.strip()}”" if query and query.strip() else None,
               f"kategorija {category.strip()}" if category and category.strip() else None]
    description = " · ".join([*(f for f in filters if f), f"aktivni oglasi na dan {stats.today:%d. %m. %Y.}"])
    return JobsByCountyDTO(
        title="Oglasi po županijama",
        description=description[0].upper() + description[1:],
        today=stats.today,
        total_jobs=stats.jobs,
        total_workers_needed=stats.workers_needed,
        counties_total=len(stats.counties),
        counties=tuple(
            CountyShareDTO(
                code=county.code, name=county.name, short_name=county.name.removesuffix(" županija"),
                jobs=county.jobs, workers_needed=county.workers_needed,
                share=round(100 * county.jobs / stats.jobs, 1) if stats.jobs else 0.0,
            )
            for county in stats.counties[:top]
        ),
        coverage=stats.coverage,
    )
