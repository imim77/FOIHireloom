from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Self

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.dao.concrete.sqla_county import SqlAlchemyCountyRepository
from FOIHireloom.dao.concrete.sqla_dzs_import import SqlAlchemyDzsImportRepository
from FOIHireloom.dao.concrete.sqla_dzs_indicator_value import SqlAlchemyDzsIndicatorValueRepository
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.dao.concrete.sqla_job_feed_membership import SqlAlchemyJobFeedMembershipRepository
from FOIHireloom.dao.concrete.sqla_source_feed import SqlAlchemySourceFeedRepository
from FOIHireloom.dao.concrete.sqla_sync_run import SqlAlchemySyncRunRepository
from FOIHireloom.dao.interfaces.county import CountyRepository
from FOIHireloom.dao.interfaces.dzs_import import DzsImportRepository
from FOIHireloom.dao.interfaces.dzs_indicator_value import DzsIndicatorValueRepository
from FOIHireloom.dao.interfaces.job import JobRepository
from FOIHireloom.dao.interfaces.job_feed_membership import JobFeedMembershipRepository
from FOIHireloom.dao.interfaces.source_feed import SourceFeedRepository
from FOIHireloom.dao.interfaces.sync_run import SyncRunRepository
from FOIHireloom.db.session import SessionManager
from FOIHireloom.exceptions import ConflictError, PersistenceError

from .base import UnitOfWork


@dataclass(frozen=True)
class SessionRepositories:
    """SessionRepositories holds the repositories of one Unit of Work context.

    Binding them together keeps every repository on the same session, and
    lets the Unit of Work drop them all at once when its context ends.
    """

    counties: CountyRepository
    dzs_imports: DzsImportRepository
    dzs_indicator_values: DzsIndicatorValueRepository
    jobs: JobRepository
    job_feed_memberships: JobFeedMembershipRepository
    source_feeds: SourceFeedRepository
    sync_runs: SyncRunRepository

    @classmethod
    def bind(cls, session: AsyncSession) -> Self:
        return cls(
            counties=SqlAlchemyCountyRepository(session),
            dzs_imports=SqlAlchemyDzsImportRepository(session),
            dzs_indicator_values=SqlAlchemyDzsIndicatorValueRepository(session),
            jobs=SqlAlchemyJobRepository(session),
            job_feed_memberships=SqlAlchemyJobFeedMembershipRepository(session),
            source_feeds=SqlAlchemySourceFeedRepository(session),
            sync_runs=SqlAlchemySyncRunRepository(session),
        )


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Create a session and its repositories for each async context.

    Instances can be reused sequentially. Use a separate instance for each
    concurrent task, and use repositories only while their context is active.

    Example:
        async with SqlAlchemyUnitOfWork(sessions) as work:
            await work.jobs.create_many(jobs, await work.transaction_time())
            await work.commit()
    """

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions
        self._context: AsyncSession | None = None
        self._session: AsyncSession | None = None
        self._repositories: SessionRepositories | None = None

    @property
    def counties(self) -> CountyRepository:
        return self._active_repositories().counties

    @property
    def dzs_imports(self) -> DzsImportRepository:
        return self._active_repositories().dzs_imports

    @property
    def dzs_indicator_values(self) -> DzsIndicatorValueRepository:
        return self._active_repositories().dzs_indicator_values

    @property
    def jobs(self) -> JobRepository:
        return self._active_repositories().jobs

    @property
    def job_feed_memberships(self) -> JobFeedMembershipRepository:
        return self._active_repositories().job_feed_memberships

    @property
    def source_feeds(self) -> SourceFeedRepository:
        return self._active_repositories().source_feeds

    @property
    def sync_runs(self) -> SyncRunRepository:
        return self._active_repositories().sync_runs

    async def __aenter__(self) -> Self:
        if self._context is not None:
            raise RuntimeError("Unit of Work is already active.")

        context = self._sessions.session()
        self._context = context
        try:
            self._session = await context.__aenter__()
            self._repositories = SessionRepositories.bind(self._session)
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

    def _active_repositories(self) -> SessionRepositories:
        if self._repositories is None:
            raise RuntimeError("Repositories require an active Unit of Work.")
        return self._repositories

    @staticmethod
    def _translate(error: SQLAlchemyError) -> PersistenceError:
        if isinstance(error, IntegrityError):
            return ConflictError(str(error))
        return PersistenceError(str(error))

    def _clear_context(self) -> None:
        self._repositories = None
        self._session = None
        self._context = None


class SqlAlchemyUnitOfWorkFactory:
    """Create an independent Unit of Work for each service operation."""

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._sessions)
