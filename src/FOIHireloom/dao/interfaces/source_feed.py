from abc import ABC, abstractmethod
from uuid import UUID

from FOIHireloom.db.models import SourceFeed
from FOIHireloom.dto.source_feed import SourceFeedCreateDTO, SourceFeedDTO, SourceFeedUpdateDTO


class SourceFeedRepository(ABC):
    """Access Croatian county source feeds in a transaction owned by the caller.

    Read methods exclude EU feeds, including when legacy rows exist in the
    database. Disabled county feeds remain available through individual lookups.
    """

    @abstractmethod
    async def get_by_id(self, feed_id: int) -> SourceFeed | None:
        """Return the county feed with this ID, or None if it is absent."""

    @abstractmethod
    async def get_by_ckan_resource_id(self, resource_id: UUID) -> SourceFeed | None:
        """Return the county feed for this CKAN resource, or None if absent."""

    @abstractmethod
    async def get_by_feed_url(self, feed_url: str) -> SourceFeed | None:
        """Return the county feed for this URL, including disabled feeds."""

    @abstractmethod
    async def list_enabled(self) -> list[SourceFeed]:
        """Return enabled county feeds ordered by ascending database ID."""

    @abstractmethod
    async def add(self, feed: SourceFeed) -> None:
        """Add and flush a county feed without committing the transaction.

        Generated fields are available after the call. Unsupported scopes raise
        ValueError. Database errors propagate; the caller owns rollback.
        """

    @abstractmethod
    async def create(self, feed: SourceFeedCreateDTO) -> SourceFeedDTO:
        """Add and flush an enabled county feed; return it with generated fields."""

    @abstractmethod
    async def update(self, feed_id: int, changes: SourceFeedUpdateDTO) -> SourceFeedDTO:
        """Apply registration metadata to an existing county feed and flush.

        Enabled flags and sync timestamps are kept. Raise NotFoundError when no
        county feed has this ID. Database errors propagate; the caller owns
        rollback.
        """
