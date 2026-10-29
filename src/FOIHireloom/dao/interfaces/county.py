from abc import ABC, abstractmethod

from FOIHireloom.db.models import County


class CountyRepository(ABC):
    """Access county reference data in the caller's transaction."""

    @abstractmethod
    async def get_by_code(self, code: str) -> County | None:
        """Return the county with this application code, or None."""

    @abstractmethod
    async def get_by_name(self, name: str) -> County | None:
        """Return the county with this exact name, or None."""

    @abstractmethod
    async def add(self, county: County) -> None:
        """Add and flush without committing; database errors propagate."""
