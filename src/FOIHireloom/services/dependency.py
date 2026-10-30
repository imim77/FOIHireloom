from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.exc import SQLAlchemyError

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import PostgresDatabase
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.factories.job_search import JobSearchServiceFactory
from FOIHireloom.factories.job_sync import JobSyncServiceFactory
from FOIHireloom.factories.source_feed_registration import SourceFeedRegistrationServiceFactory
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface

USER_AGENT = "FOIHireloom/0.1 (+https://github.com/imim77/FOIHireloom)"


class DependencyService:
    """Own the infrastructure behind services for commands and API handlers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @asynccontextmanager
    async def source_feed_registration_service(
        self, *, with_database: bool = True
    ) -> AsyncIterator[SourceFeedRegistrationServiceInterface]:
        """Yield a registration service and close its HTTP client and engine.

        with_database=False never constructs a database engine; the service
        can then only preview sources.
        """
        factory = SourceFeedRegistrationServiceFactory(self._settings)
        async with httpx.AsyncClient() as http:
            if not with_database:
                yield factory.create(http, None)
                return
            async with self._unit_of_work_factory() as uow_factory:
                yield factory.create(http, uow_factory)

    @asynccontextmanager
    async def job_sync_service(self) -> AsyncIterator[JobSyncServiceInterface]:
        """Yield a sync service sharing one HTTP client, and its HZZ cookie, for the whole run."""
        factory = JobSyncServiceFactory(self._settings)
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as http:
            async with self._unit_of_work_factory() as uow_factory:
                yield factory.create(http, uow_factory)

    @asynccontextmanager
    async def job_search_service(self) -> AsyncIterator[JobSearchServiceInterface]:
        """Yield a read-only search service; keep it open for as long as requests arrive."""
        async with self._unit_of_work_factory() as uow_factory:
            yield JobSearchServiceFactory().create(uow_factory)

    @asynccontextmanager
    async def _unit_of_work_factory(self) -> AsyncIterator[SqlAlchemyUnitOfWorkFactory]:
        try:
            database = PostgresDatabase(self._settings)
        except SQLAlchemyError as error:
            raise PersistenceError("Invalid database configuration.") from error
        try:
            yield SqlAlchemyUnitOfWorkFactory(SessionManager(database.engine))
        finally:
            await database.close()
