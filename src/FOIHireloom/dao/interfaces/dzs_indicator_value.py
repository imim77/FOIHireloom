from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from FOIHireloom.dto.dzs import DzsValueChangeDTO, DzsValueDTO, DzsValueSnapshotDTO


class DzsIndicatorValueRepository(ABC):
    """Access stored DZS county values in the caller's transaction."""

    @abstractmethod
    async def list_snapshots(self) -> list[DzsValueSnapshotDTO]:
        """Return every stored value with its county's ISO code."""

    @abstractmethod
    async def create_many(self, values: Sequence[DzsValueDTO], import_id: int, written_at: datetime) -> None:
        """Insert county values written by the import at written_at.

        Raise ValueError before writing if a value has no county or names an
        ISO code that no stored county has. Database errors propagate.
        """

    @abstractmethod
    async def update_many(self, changes: Sequence[DzsValueChangeDTO], import_id: int, written_at: datetime) -> None:
        """Rewrite the content of existing rows by ID; a revised row also gets revised_at = written_at."""
