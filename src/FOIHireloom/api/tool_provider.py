from abc import ABC, abstractmethod

from fastmcp import FastMCP

# Ovo je isto ko Interface u C#/Java
class ToolGroup(ABC):
    @abstractmethod
    def register(self, server: FastMCP) -> None:
        pass
