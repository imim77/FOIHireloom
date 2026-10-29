from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import SourceFeed, SyncRun
from FOIHireloom.persistence.sync_run_repository import SyncRunRepository


class SqlAlchemySyncRunRepository(SyncRunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, run_id: int) -> SyncRun | None:
        statement = select(SyncRun).join(SourceFeed).where(
            SyncRun.id == run_id,
            SourceFeed.scope == "county",
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_for_feed(self, feed_id: int) -> SyncRun | None:
        statement = (
            select(SyncRun)
            .join(SourceFeed)
            .where(SyncRun.feed_id == feed_id, SourceFeed.scope == "county")
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, sync_run: SyncRun) -> None:
        feed_id = await self._session.scalar(select(SourceFeed.id).where(
            SourceFeed.id == sync_run.feed_id,
            SourceFeed.scope == "county",
        ))
        if feed_id is None:
            raise ValueError("Sync attempts require an existing Croatian county source feed.")
        self._session.add(sync_run)
        await self._session.flush()
