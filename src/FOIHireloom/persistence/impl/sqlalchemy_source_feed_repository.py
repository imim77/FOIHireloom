from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import SourceFeed
from FOIHireloom.persistence.source_feed_repository import SourceFeedRepository


class SqlAlchemySourceFeedRepository(SourceFeedRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, feed_id: int) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope == "county",
            SourceFeed.id == feed_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_ckan_resource_id(self, resource_id: UUID) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope == "county",
            SourceFeed.ckan_resource_id == resource_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_feed_url(self, feed_url: str) -> SourceFeed | None:
        statement = select(SourceFeed).where(
            SourceFeed.scope == "county", SourceFeed.feed_url == feed_url
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[SourceFeed]:
        statement = (
            select(SourceFeed)
            .where(SourceFeed.scope == "county", SourceFeed.enabled.is_(True))
            .order_by(SourceFeed.id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def add(self, feed: SourceFeed) -> None:
        if feed.scope != "county":
            raise ValueError("Only Croatian county source feeds can be added.")
        self._session.add(feed)
        await self._session.flush()
