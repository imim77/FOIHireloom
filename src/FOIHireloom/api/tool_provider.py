from abc import ABC, abstractmethod

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

# Ovo je isto ko Interface u C#/Java
class ToolGroup(ABC):
    @abstractmethod
    def register(self, server: FastMCP) -> None:
        pass
