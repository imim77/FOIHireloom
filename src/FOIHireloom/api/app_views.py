from fastmcp import FastMCP

from .apps.views import VIEWS
from .tool_provider import ToolGroup


class AppViews(ToolGroup):
    """Serve every MCP App page as a ui:// resource; tools point at one through AppConfig(resource_uri=view.uri).

    The pages load nothing from the web, so they need no CSP exceptions.
    """

    def register(self, server: FastMCP) -> None:
        for view in VIEWS:
            server.resource(view.uri, name=view.name, description=view.description)(view.page)
