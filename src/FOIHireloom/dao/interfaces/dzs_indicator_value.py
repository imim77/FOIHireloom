from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence
from datetime import date

from FOIHireloom.dto.dzs import (
    DzsIndicator,
    DzsSex,
    DzsStoredValueDTO,
    DzsValueChangeDTO,
    DzsValueDTO,
    DzsValueSnapshotDTO,
)


class DzsIndicatorValueRepository(ABC):
    """Access stored DZS county values in the caller's transaction."""

    @abstractmethod
    async def list_snapshots(self) -> list[DzsValueSnapshotDTO]:
        """Return every stored value with its county's ISO code."""

    @abstractmethod
    async def create_many(self, values: Sequence[DzsValueDTO], import_id: int) -> None:
        """Insert county values written by the import.

        Raise ValueError before writing if a value has no county or names an
        ISO code that no stored county has. Database errors propagate.
        """

    @abstractmethod
    async def update_many(self, changes: Sequence[DzsValueChangeDTO], import_id: int) -> None:
        """Rewrite existing rows by ID and record the import that supplied their content."""

    @abstractmethod
    async def list_values(
        self, county_ids: Collection[int], indicators: Collection[DzsIndicator], sex: DzsSex,
        periods: Collection[date],
    ) -> list[DzsStoredValueDTO]:
        """Return the stored values of these counties, indicators and months for one sex, known or not.

        A month without a stored row has no entry.
        """

    @abstractmethod
    async def list_series(
        self, county_ids: Collection[int], indicator: DzsIndicator, sex: DzsSex, first: date, last: date,
    ) -> list[DzsStoredValueDTO]:
        """Return the stored values of one indicator and sex for the months first to last, both included, by month."""

    @abstractmethod
    async def latest_common_periods(
        self, county_ids: Collection[int], indicators: Collection[DzsIndicator], sex: DzsSex,
    ) -> dict[DzsIndicator, date]:
        """Return, per indicator, the latest month with a known value for every one of county_ids.

        An indicator without such a month is left out.
        """
