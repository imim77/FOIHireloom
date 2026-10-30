"""Run `uv run --locked foihireloom-mcp [--transport stdio|http] [--host H] [--port P] [--path /mcp]`.

    Options override the MCP_* settings from the environment or .env.
"""

import argparse

from FOIHireloom.api.mcp_server import McpServer
from FOIHireloom.config.settings import Settings


def settings_from_args(argv: list[str] | None = None) -> Settings:
    parser = argparse.ArgumentParser(description="Serve the FOIHireloom job search tools over MCP.")
    parser.add_argument("--transport", choices=["stdio", "http"], help="stdio for local clients, http for Streamable HTTP.")
    parser.add_argument("--host", help="Address the HTTP server binds to.")
    parser.add_argument("--port", type=int, help="Port of the HTTP server.")
    parser.add_argument("--path", help="Path of the MCP endpoint, e.g. /mcp.")
    args = parser.parse_args(argv)
    overrides = {
        "MCP_TRANSPORT": args.transport, "MCP_HOST": args.host, "MCP_PORT": args.port, "MCP_PATH": args.path,
    }
    return Settings(**{name: value for name, value in overrides.items() if value is not None})


def main(argv: list[str] | None = None) -> None:
    McpServer(settings_from_args(argv)).run()


if __name__ == "__main__":
    main()
