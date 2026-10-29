from datetime import datetime
from types import TracebackType
from typing import Self

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.session import AsyncDBContextManager, SessionManager
from FOIHireloom.dao.interfaces.county import CountyRepository
from FOIHireloom.dao.concrete.sqla_county import SqlAlchemyCountyRepository
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.dao.concrete.sqla_job_feed_membership import (
    SqlAlchemyJobFeedMembershipRepository,
)
from FOIHireloom.dao.concrete.sqla_source_feed import SqlAlchemySourceFeedRepository
from FOIHireloom.dao.concrete.sqla_sync_run import SqlAlchemySyncRunRepository
from FOIHireloom.dao.interfaces.job import JobRepository
from FOIHireloom.dao.interfaces.job_feed_membership import JobFeedMembershipRepository
from FOIHireloom.dao.interfaces.source_feed import SourceFeedRepository
from FOIHireloom.dao.interfaces.sync_run import SyncRunRepository

from FOIHireloom.exceptions import ConflictError, PersistenceError

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
        self._counties: CountyRepository | None = None
        self._jobs: JobRepository | None = None
        self._job_feed_memberships: JobFeedMembershipRepository | None = None
        self._source_feeds: SourceFeedRepository | None = None
        self._sync_runs: SyncRunRepository | None = None

    @property
    def counties(self) -> CountyRepository:
        if self._counties is None:
            raise RuntimeError("County repository requires an active Unit of Work.")
        return self._counties

    @property
    def jobs(self) -> JobRepository:
        if self._jobs is None:
            raise RuntimeError("Job repository requires an active Unit of Work.")
        return self._jobs

    @property
    def job_feed_memberships(self) -> JobFeedMembershipRepository:
        if self._job_feed_memberships is None:
            raise RuntimeError("Job feed membership repository requires an active Unit of Work.")
        return self._job_feed_memberships

    @property
    def source_feeds(self) -> SourceFeedRepository:
        if self._source_feeds is None:
            raise RuntimeError("Source feed repository requires an active Unit of Work.")
        return self._source_feeds

    @property
    def sync_runs(self) -> SyncRunRepository:
        if self._sync_runs is None:
            raise RuntimeError("Sync run repository requires an active Unit of Work.")
        return self._sync_runs

    async def __aenter__(self) -> Self:
        if self._context is not None:
            raise RuntimeError("Unit of Work is already active.")

        context = self._sessions.session()
        self._context = context
        try:
            self._session = await context.__aenter__()
            self._counties = SqlAlchemyCountyRepository(self._session)
            self._jobs = SqlAlchemyJobRepository(self._session)
            self._job_feed_memberships = SqlAlchemyJobFeedMembershipRepository(self._session)
            self._source_feeds = SqlAlchemySourceFeedRepository(self._session)
            self._sync_runs = SqlAlchemySyncRunRepository(self._session)
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
        if isinstance(exc, SQLAlchemyError):
            raise self._translate(exc) from exc

    async def transaction_time(self) -> datetime:
        return await self._active_session().scalar(select(func.now()))

    async def commit(self) -> None:
        try:
            await self._active_session().commit()
        except SQLAlchemyError as error:
            raise self._translate(error) from error

    async def rollback(self) -> None:
        await self._active_session().rollback()

    def _active_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of Work is not active. Use 'async with'.")
        return self._session

    @staticmethod
    def _translate(error: SQLAlchemyError) -> PersistenceError:
        if isinstance(error, IntegrityError):
            return ConflictError(str(error))
        return PersistenceError(str(error))

    def _clear_context(self) -> None:
        self._counties = None
        self._jobs = None
        self._job_feed_memberships = None
        self._source_feeds = None
        self._sync_runs = None
        self._session = None
        self._context = None


class SqlAlchemyUnitOfWorkFactory:
    """Create an independent Unit of Work for each service operation."""

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._sessions)
