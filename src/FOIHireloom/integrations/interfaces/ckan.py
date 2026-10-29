from abc import ABC, abstractmethod

from FOIHireloom.dto.ckan import CkanResource


class CkanClientInterface(ABC):
    """Read dataset metadata from a CKAN catalogue."""

    @abstractmethod
    async def get_resources(self, dataset_id: str) -> list[CkanResource]:
        """Return the dataset's resources unfiltered.

        Raise ValueError for a blank dataset ID and CkanError when CKAN cannot
        supply a valid package_show response.
        """
