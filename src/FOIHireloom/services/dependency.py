from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.exc import SQLAlchemyError

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import PostgresDatabase
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.factories.source_feed_registration import SourceFeedRegistrationServiceFactory
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface


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
            try:
                database = PostgresDatabase(self._settings)
            except SQLAlchemyError as error:
                raise PersistenceError("Invalid database configuration.") from error
            try:
                yield factory.create(http, SqlAlchemyUnitOfWorkFactory(SessionManager(database.engine)))
            finally:
                await database.close()
