"""The MCP App pages: one self-contained HTML file per view, built from frontend/ into views/.

`npm run build` in frontend/ writes views/<name>.html with its scripts,
styles and the MCP Apps SDK inlined, so a page loads nothing from the web.
The built pages are committed, so the server runs without Node.
"""

import hashlib
from dataclasses import dataclass
from functools import cached_property
from importlib.resources import files


@dataclass(frozen=True)
class AppView:
    # The page's file name in views/ without .html, as in frontend/src/views/.
    name: str
    description: str

    def page(self) -> str:
        page = files(__package__).joinpath("views", f"{self.name}.html")
        if not page.is_file():
            raise FileNotFoundError(f"MCP App page {self.name}.html is missing; run npm run build in frontend/.")
        return page.read_text(encoding="utf-8")

    @cached_property
    def uri(self) -> str:
        # Hosts cache a page by its URI (Claude did not reread a changed page), so the URI names the page's version.
        return f"ui://foihireloom/{self.name}-{hashlib.sha256(self.page().encode()).hexdigest()[:12]}.html"


JOBS_BY_COUNTY = AppView("jobs-by-county", "Chart page for show_jobs_by_county.")

VIEWS = (JOBS_BY_COUNTY,)
