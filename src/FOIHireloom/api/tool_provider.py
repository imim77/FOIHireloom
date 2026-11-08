from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, ClassVar

from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from FOIHireloom.exceptions import FOIHireloomException, PersistenceError

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
DATA_ONLY = AppConfig(visibility=["app"])


class ToolGroup(ABC):
    """ToolGroup adds one cohesive set of tools or resources to a server.

    A new tool or view is a new group in mcp_server.TOOL_GROUPS; existing
    groups stay unchanged.
    """

    @abstractmethod
    def register(self, server: FastMCP) -> None:
        pass

    @staticmethod
    def _add_tool(server: FastMCP, tool: Callable[..., Any], app: AppConfig | None = None) -> None:
        server.tool(app=app, annotations=READ_ONLY)(tool)


class ServiceToolGroup[S](ToolGroup):
    """ServiceToolGroup runs its tools on one service from the server's lifespan context.

    Tools only translate arguments and errors; the service holds the rules.
    Subclasses set _service_key, the lifespan key of the service;
    _caller_errors, the errors whose details the caller can act on; and
    _unavailable_message, said instead of a database failure, whose details
    stay in the server log.
    """

    _service_key: ClassVar[str]
    _caller_errors: ClassVar[tuple[type[FOIHireloomException], ...]]
    _unavailable_message: ClassVar[str]

    def _service(self, ctx: Context) -> S:
        return ctx.lifespan_context[self._service_key]

    async def _call[T](self, operation: Awaitable[T]) -> T:
        try:
            return await operation
        except self._caller_errors as error:
            raise ToolError(error.details) from error
        except PersistenceError as error:
            raise ToolError(self._unavailable_message) from error


def tool_arguments(scope: Mapping[str, Any], *omitted: str) -> dict[str, Any]:
    """tool_arguments returns a tool method's arguments from its locals(), without self, ctx and omitted.

    Call it before the tool assigns any local. Omit every argument that is
    not a field of the DTO built from them: the DTOs ignore unknown keys, but
    an argument sharing a field's name, as show_jobs_by_county's top, would
    set that field.
    """
    return {name: value for name, value in scope.items() if name not in {"self", "ctx", *omitted}}
