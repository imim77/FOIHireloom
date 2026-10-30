"""The jobs-by-county chart: a ui:// page that draws counties as 3D columns, by jobs or by workers sought.

The tool returns JobsByCountyDTO as structured content; the host loads the
page in a sandboxed iframe and passes it that result over the MCP Apps
bridge. Text-only hosts still get the same data.
"""

import hashlib
from importlib.resources import files

from FOIHireloom.dto.job_market import CountyMetric, CountyShareDTO, JobMarketStatsDTO, JobsByCountyDTO

# The page loads the MCP Apps SDK from this origin, so its CSP must allow it.
SDK_ORIGIN = "https://unpkg.com"
DEFAULT_TOP = 7
# There are 21 counties.
MAX_TOP = 21
TITLES: dict[CountyMetric, str] = {
    "jobs": "Broj oglasa po županijama",
    "workers_needed": "Broj traženih radnika po županijama",
}


def page() -> str:
    return files(__package__).joinpath("jobs_by_county.html").read_text(encoding="utf-8")


# Hosts cache a page by its URI (Claude did not reread a changed page), so the URI names the page's version.
RESOURCE_URI = f"ui://foihireloom/jobs-by-county-{hashlib.sha256(page().encode()).hexdigest()[:12]}.html"


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
