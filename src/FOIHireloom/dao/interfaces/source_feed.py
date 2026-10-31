from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from FOIHireloom.db.models import SourceFeed
from FOIHireloom.dto.job_sync import FeedCheckDTO
from FOIHireloom.dto.source_feed import (
    FeedCategoryMappingDTO,
    SourceFeedCreateDTO,
    SourceFeedDTO,
    SourceFeedUpdateDTO,
)


class SourceFeedRepository(ABC):
    """Access Croatian county and occupation source feeds in a transaction
    owned by the caller.

    Read methods exclude EU feeds, including when legacy rows exist in the
    database. Disabled feeds remain available through individual lookups.
    """

    @abstractmethod
    async def get_by_id(self, feed_id: int) -> SourceFeed | None:
        """Return the county or occupation feed with this ID, or None if it is absent."""

    @abstractmethod
    async def get_by_ckan_resource_id(self, resource_id: UUID) -> SourceFeed | None:
        """Return the county or occupation feed for this CKAN resource, or None if absent."""

    @abstractmethod
    async def get_by_feed_url(self, feed_url: str) -> SourceFeed | None:
        """Return the county or occupation feed for this URL, including disabled feeds."""

    @abstractmethod
    async def list_enabled(self) -> list[SourceFeed]:
        """Return enabled feeds, county feeds first, each ordered by database ID.

        Occupation feeds only link jobs that county feeds have imported, so
        a sync must read the county feeds first.
        """

    @abstractmethod
    async def list_synced(self) -> list[SourceFeed]:
        """Return every county and occupation feed, enabled or not, ordered by database ID."""

    @abstractmethod
    async def add(self, feed: SourceFeed) -> None:
        """Add and flush a county or occupation feed without committing the transaction.

        Generated fields are available after the call. Unsupported scopes raise
        ValueError. Database errors propagate; the caller owns rollback.
        """

    @abstractmethod
    async def create(self, feed: SourceFeedCreateDTO) -> SourceFeedDTO:
        """Add and flush an enabled feed; return it with generated fields."""

    @abstractmethod
    async def update(self, feed_id: int, changes: SourceFeedUpdateDTO) -> SourceFeedDTO:
        """Apply registration metadata to an existing feed and flush.

        Enabled flags and sync timestamps are kept; resetting the HTTP
        validators also clears the category mapping. Raise NotFoundError when no
        county or occupation feed has this ID, and ValueError when the scope
        differs. Database errors propagate; the caller owns rollback.
        """

    @abstractmethod
    async def record_check(self, feed_id: int, check: FeedCheckDTO, checked_at: datetime) -> None:
        """Store a check's time and, when it succeeded, its validators.

        Raise NotFoundError when no county or occupation feed has this ID.
        """

    @abstractmethod
    async def record_category_mapping(
        self, feed_id: int, mapping: FeedCategoryMappingDTO, verified_at: datetime
    ) -> None:
        """Replace an occupation feed's category mapping with this verification.

        Raise NotFoundError when no county or occupation feed has this ID, and
        ValueError for a county feed.
        """
