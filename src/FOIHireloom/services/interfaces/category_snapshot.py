from abc import ABC, abstractmethod

from FOIHireloom.dto.category_snapshot import CategorySnapshotDTO


class CategorySnapshotServiceInterface(ABC):
    """Record the category fill of listed jobs as a reference snapshot."""

    @abstractmethod
    async def take(self) -> CategorySnapshotDTO:
        """Read the synced feeds and every listed job's category inputs and result, and count the coverage."""
