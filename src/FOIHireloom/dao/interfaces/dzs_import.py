from abc import ABC, abstractmethod
from datetime import datetime

from FOIHireloom.db.models import DzsImport
from FOIHireloom.dto.dzs import DzsImportOutcomeDTO


class DzsImportRepository(ABC):
    """Access DZS import runs in the caller's transaction.

    Persist failure outcomes in a separate transaction after rolling back the
    import's writes, so that the audit record survives the failed import.
    """

    @abstractmethod
    async def get_by_id(self, import_id: int) -> DzsImport | None:
        """Return the run with its files loaded, or None if absent."""

    @abstractmethod
    async def start(self) -> int:
        """Add a running import started at the transaction time; return its ID."""

    @abstractmethod
    async def finish(self, import_id: int, outcome: DzsImportOutcomeDTO, finished_at: datetime) -> None:
        """Complete a running import and add its files; raise NotFoundError for an unknown ID."""
