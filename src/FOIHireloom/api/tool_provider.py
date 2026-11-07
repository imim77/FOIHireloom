from abc import ABC, abstractmethod

from fastmcp import FastMCP
from fastmcp.apps import AppConfig
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
# Keep data-only counterparts callable by apps without competing for model routing.
DATA_ONLY = AppConfig(visibility=["app"])

# Ovo je isto ko Interface u C#/Java
class ToolGroup(ABC):
    @abstractmethod
    def register(self, server: FastMCP) -> None:
        pass
