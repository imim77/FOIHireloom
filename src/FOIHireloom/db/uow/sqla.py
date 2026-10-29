from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.session import AsyncDBContextManager, SessionManager
from FOIHireloom.persistence.impl.sqlalchemy_job_repository import SqlAlchemyJobRepository
from FOIHireloom.persistence.impl.sqlalchemy_source_feed_repository import SqlAlchemySourceFeedRepository
from FOIHireloom.persistence.job_repository import JobRepository
from FOIHireloom.persistence.source_feed_repository import SourceFeedRepository

from .base import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Create a session and its repositories for each async context.

    Instances can be reused sequentially. Use a separate instance for each
    concurrent task, and use repositories only while their context is active.

    Example:
        async with SqlAlchemyUnitOfWork(sessions) as work:
            await work.jobs.add(job)
            await work.commit()
    """

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions
        self._context: AsyncDBContextManager | None = None
        self._session: AsyncSession | None = None
        self._jobs: JobRepository | None = None
        self._source_feeds: SourceFeedRepository | None = None

    @property
    def jobs(self) -> JobRepository:
        if self._jobs is None:
            raise RuntimeError("Job repository requires an active Unit of Work.")
        return self._jobs

    @property
    def source_feeds(self) -> SourceFeedRepository:
        if self._source_feeds is None:
            raise RuntimeError("Source feed repository requires an active Unit of Work.")
        return self._source_feeds

    async def __aenter__(self) -> Self:
        if self._context is not None:
            raise RuntimeError("Unit of Work is already active.")

        context = self._sessions.session()
        self._context = context
        try:
            self._session = await context.__aenter__()
            self._jobs = SqlAlchemyJobRepository(self._session)
            self._source_feeds = SqlAlchemySourceFeedRepository(self._session)
        except BaseException as error:
            try:
                await context.__aexit__(type(error), error, error.__traceback__)
            finally:
                self._clear_context()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        context = self._context
        if context is None:
            raise RuntimeError("Unit of Work is not active.")
        try:
            await self.rollback()
        finally:
            try:
                await context.__aexit__(exc_type, exc, tb)
            finally:
                self._clear_context()

    async def commit(self) -> None:
        await self._active_session().commit()

    async def rollback(self) -> None:
        await self._active_session().rollback()

    def _active_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of Work is not active. Use 'async with'.")
        return self._session

    def _clear_context(self) -> None:
        self._jobs = None
        self._source_feeds = None
        self._session = None
        self._context = None
