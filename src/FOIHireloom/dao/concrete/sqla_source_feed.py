from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import SourceFeed
from FOIHireloom.db.models.source_feed import SYNCED_SCOPES
from FOIHireloom.dto.job_sync import FeedCheckDTO
from FOIHireloom.dto.source_feed import (
    FeedCategoryMappingDTO,
    SourceFeedCreateDTO,
    SourceFeedDTO,
    SourceFeedUpdateDTO,
)
from FOIHireloom.exceptions import NotFoundError
from FOIHireloom.dao.interfaces.source_feed import SourceFeedRepository


class SqlAlchemySourceFeedRepository(SourceFeedRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, feed_id: int) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope.in_(SYNCED_SCOPES),
            SourceFeed.id == feed_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_ckan_resource_id(self, resource_id: UUID) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope.in_(SYNCED_SCOPES),
            SourceFeed.ckan_resource_id == resource_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_feed_url(self, feed_url: str) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope.in_(SYNCED_SCOPES), SourceFeed.feed_url == feed_url
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[SourceFeed]:
        statement = (
            select(SourceFeed)
            .where(SourceFeed.scope.in_(SYNCED_SCOPES), SourceFeed.enabled.is_(True))
            .order_by(SourceFeed.scope != "county", SourceFeed.id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def add(self, feed: SourceFeed) -> None:
        if feed.scope not in SYNCED_SCOPES:
            raise ValueError("Only Croatian county and occupation source feeds can be added.")
        self._session.add(feed)
        await self._session.flush()

    async def create(self, feed: SourceFeedCreateDTO) -> SourceFeedDTO:
        entity = SourceFeed(**feed.model_dump())
        await self.add(entity)
        return SourceFeedDTO.model_validate(entity)

    async def update(self, feed_id: int, changes: SourceFeedUpdateDTO) -> SourceFeedDTO:
        feed = await self.get_by_id(feed_id)
        if feed is None:
            raise NotFoundError("source feed", str(feed_id))
        if feed.scope != changes.scope:
            raise ValueError("A source feed cannot change its scope.")
        feed.county_id, feed.ckan_resource_id = changes.county_id, changes.ckan_resource_id
        feed.label, feed.feed_url = changes.label, changes.feed_url
        if changes.reset_http_validators:
            feed.etag = feed.source_last_modified_at = None
            feed.mapped_category = feed.mapping_status = feed.mapping_verified_at = None
            feed.mapping_matching_examples = feed.mapping_contradicting_examples = None
        await self._session.flush()
        return SourceFeedDTO.model_validate(feed)

    async def record_check(self, feed_id: int, check: FeedCheckDTO, checked_at: datetime) -> None:
        feed = await self.get_by_id(feed_id)
        if feed is None:
            raise NotFoundError("source feed", str(feed_id))
        feed.last_checked_at = checked_at
        if check.succeeded:
            feed.last_success_at = checked_at
            feed.etag, feed.source_last_modified_at = check.etag, check.source_last_modified_at
            if check.content_changed:
                feed.last_content_change_at = checked_at
        await self._session.flush()

    async def record_category_mapping(
        self, feed_id: int, mapping: FeedCategoryMappingDTO, verified_at: datetime
    ) -> None:
        feed = await self.get_by_id(feed_id)
        if feed is None:
            raise NotFoundError("source feed", str(feed_id))
        if feed.scope != "occupation":
            raise ValueError("Only occupation feeds have a category mapping.")
        feed.mapped_category, feed.mapping_status = mapping.category, mapping.status
        feed.mapping_matching_examples = mapping.matching_examples
        feed.mapping_contradicting_examples = mapping.contradicting_examples
        feed.mapping_verified_at = verified_at
        await self._session.flush()
