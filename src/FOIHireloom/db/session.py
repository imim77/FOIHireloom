from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class SessionManager:
    def __init__(self, engine: AsyncEngine) -> None:
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    def session(self) -> "AsyncDBContextManager":
        return AsyncDBContextManager(self._session_factory)


class AsyncDBContextManager:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session: AsyncSession = session_factory()

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._session.close()
