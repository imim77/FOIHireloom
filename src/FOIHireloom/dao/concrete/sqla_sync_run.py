from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import SourceFeed, SyncRun
from FOIHireloom.db.models.source_feed import SYNCED_SCOPES
from FOIHireloom.dao.interfaces.sync_run import SyncRunRepository
from FOIHireloom.dto.job_sync import SyncRunOutcomeDTO
from FOIHireloom.exceptions import NotFoundError


class SqlAlchemySyncRunRepository(SyncRunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, run_id: int) -> SyncRun | None:
        statement = select(SyncRun).join(SourceFeed).where(
            SyncRun.id == run_id,
            SourceFeed.scope.in_(SYNCED_SCOPES),
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_for_feed(self, feed_id: int) -> SyncRun | None:
        statement = (
            select(SyncRun)
            .join(SourceFeed)
            .where(SyncRun.feed_id == feed_id, SourceFeed.scope.in_(SYNCED_SCOPES))
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, sync_run: SyncRun) -> None:
        feed_id = await self._session.scalar(select(SourceFeed.id).where(
            SourceFeed.id == sync_run.feed_id,
            SourceFeed.scope.in_(SYNCED_SCOPES),
        ))
        if feed_id is None:
            raise ValueError("Sync attempts require an existing Croatian county or occupation source feed.")
        self._session.add(sync_run)
        await self._session.flush()

    async def start(self, feed_id: int) -> int:
        run = SyncRun(feed_id=feed_id)
        await self.add(run)
        return run.id

    async def finish(self, run_id: int, outcome: SyncRunOutcomeDTO, finished_at: datetime) -> None:
        run = await self.get_by_id(run_id)
        if run is None:
            raise NotFoundError("sync run", str(run_id))
        for field, value in outcome.model_dump().items():
            setattr(run, field, value)
        run.finished_at = finished_at
        await self._session.flush()

    async def get_latest_items_seen(self, feed_id: int) -> int | None:
        statement = (
            select(SyncRun.items_seen)
            .join(SourceFeed)
            .where(SyncRun.feed_id == feed_id, SyncRun.status == "succeeded", SourceFeed.scope.in_(SYNCED_SCOPES))
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(1)
        )
        return await self._session.scalar(statement)
