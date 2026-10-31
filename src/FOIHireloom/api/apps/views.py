"""The MCP App pages: one self-contained HTML file per view, built from frontend/ into frontend/dist/.

`npm run build` in frontend/ writes dist/<name>.html with its scripts,
styles and the MCP Apps SDK inlined, so a page loads nothing from the web.
dist/ is not committed: build it before starting the server or the tests.
"""

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[4] / "frontend"
DIST = FRONTEND / "dist"
BUILD_HINT = "run npm install and npm run build in frontend/"


@dataclass(frozen=True)
class AppView:
    # The page's file name in frontend/dist/ without .html, as in frontend/src/views/.
    name: str
    description: str

    def page(self) -> str:
        page = DIST / f"{self.name}.html"
        if not page.is_file():
            raise FileNotFoundError(f"MCP App page {page} is missing; {BUILD_HINT}.")
        return page.read_text(encoding="utf-8")

    @cached_property
    def uri(self) -> str:
        # Hosts cache a page by its URI (Claude did not reread a changed page), so the URI names the page's version.
        return f"ui://foihireloom/{self.name}-{hashlib.sha256(self.page().encode()).hexdigest()[:12]}.html"


JOBS_BY_COUNTY = AppView("jobs-by-county", "Chart page for show_jobs_by_county.")
JOB_CARDS = AppView("job-cards", "Job card page for show_jobs.")

VIEWS = (JOBS_BY_COUNTY, JOB_CARDS)


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
