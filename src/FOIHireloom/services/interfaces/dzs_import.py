from abc import ABC, abstractmethod

from FOIHireloom.dto.dzs import DzsImportResultDTO, DzsSourceDTO


class DzsImportServiceInterface(ABC):
    """Import DZS county labour-market values from a T1 release table and the county workbook."""

    @abstractmethod
    async def validate_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        """Obtain, parse and validate both files without touching the database.

        status is "validated", "rejected" when the files are invalid, or
        "failed" when one cannot be obtained.
        """

    @abstractmethod
    async def import_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        """Validate both files, then store all their county values in one transaction.

        A rejected or failed import writes no values and keeps the previous
        ones; every attempt is recorded in dzs_imports. Stored values that the
        files no longer contain are kept.
        """
