from abc import ABC, abstractmethod
from datetime import date

from FOIHireloom.db.models import County
from FOIHireloom.dto.county import CountyDefinitionDTO, CountyDTO
from FOIHireloom.dto.job_search import RegionDTO


class CountyRepository(ABC):
    """Access county reference data in the caller's transaction."""

    @abstractmethod
    async def get_by_code(self, code: str) -> County | None:
        """Return the county with this application code, or None."""

    @abstractmethod
    async def get_by_name(self, name: str) -> County | None:
        """Return the county with this exact name, or None."""

    @abstractmethod
    async def list_regions(self, open_on: date) -> list[RegionDTO]:
        """Return every county by name with its listed jobs whose known deadline is not before open_on."""

    @abstractmethod
    async def add(self, county: County) -> None:
        """Add and flush without committing; database errors propagate."""

    @abstractmethod
    async def create(self, county: CountyDefinitionDTO) -> CountyDTO:
        """Add and flush a county from its definition; return it with its ID."""
