from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from FOIHireloom.db.database import engine


async_session = async_sessionmaker(engine, expire_on_commit=False)


class AsyncDBContextManager:
    def __init__(self) -> None:
        self.db: AsyncSession = async_session()

    async def __aenter__(self) -> AsyncSession:
        return self.db

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.db.close()
