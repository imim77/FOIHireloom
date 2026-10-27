import sys

from fastmcp import FastMCP


class McpServer:
    def __init__(self) -> None:
        self.server = FastMCP("FOIHireloom")

    def run(self) -> None:
        print("Starting MCP server", file=sys.stderr)
        self.server.run()
