"""The MCP App pages: one self-contained HTML file per view, built from frontend/ into frontend/dist/.

`npm run build` in frontend/ writes dist/<name>.html with its scripts,
styles and the MCP Apps SDK inlined, so a page loads nothing from the web.
dist/ is not committed: build it before starting the server or the tests.
"""

import hashlib
import json
from functools import cached_property
from pathlib import Path

from fastmcp.apps import AppConfig

FRONTEND = Path(__file__).resolve().parents[4] / "frontend"
DIST = FRONTEND / "dist"
BUILD_HINT = "run npm install and npm run build in frontend/"


class AppView:
    """AppView is one MCP App page; a tool shows its result in the page through app_config.

    name is the page's file name in frontend/dist/ without .html, as in
    frontend/src/pages/.
    """

    def __init__(self, name: str, description: str) -> None:
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def page(self) -> str:
        page = DIST / f"{self._name}.html"
        if not page.is_file():
            raise FileNotFoundError(f"MCP App page {page} is missing; {BUILD_HINT}.")
        return page.read_text(encoding="utf-8")

    @cached_property
    def uri(self) -> str:
        return f"ui://foihireloom/{self._name}-{hashlib.sha256(self.page().encode()).hexdigest()[:12]}.html"

    @property
    def app_config(self) -> AppConfig:
        return AppConfig(resource_uri=self.uri)


JOBS_BY_COUNTY = AppView("jobs-by-county", "Chart page for show_jobs_by_county.")
JOB_CARDS = AppView("job-cards", "Job card page for show_jobs.")
JOB_COMPARISON = AppView("job-comparison", "Job comparison page for show_job_comparison.")

COUNTY_COMPARISON = AppView("county-comparison", "County comparison page for show_county_comparison.")
UNEMPLOYMENT_HISTORY = AppView("unemployment-history", "Unemployment rate chart page for show_unemployment_history.")
ACCOMMODATION_COMPARISON = AppView("accommodation-comparison", "Accommodation comparison donut for job ads.")
LABOUR_MARKET_FORECAST = AppView("labour-market-forecast", "County Chronos forecast with history and an 80% interval.")

VIEWS = (JOBS_BY_COUNTY, JOB_CARDS, JOB_COMPARISON, COUNTY_COMPARISON, UNEMPLOYMENT_HISTORY,
         ACCOMMODATION_COMPARISON, LABOUR_MARKET_FORECAST)


def stale_sources(frontend: Path = FRONTEND) -> list[str]:
    """Frontend files added, removed or changed since the last build; empty when the pages are current.

    The build records a SHA-256 of each source in dist/sources.json (see
    frontend/build-views.mjs); this hashes the same files again.
    """
    manifest = frontend / "dist" / "sources.json"
    if not manifest.is_file():
        return ["dist/sources.json"]
    built = json.loads(manifest.read_text(encoding="utf-8"))
    current = {}
    for source in built["sources"]:
        root = frontend / source
        paths = sorted(root.rglob("*")) if root.is_dir() else [root]
        for path in paths:
            relative = path.relative_to(frontend)
            if path.is_file() and not any(part.startswith(".") for part in relative.parts):
                current[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sorted(file for file in built["files"].keys() | current.keys()
                  if built["files"].get(file) != current.get(file))
