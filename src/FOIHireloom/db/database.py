from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from FOIHireloom.config.settings import Settings


class PostgresDatabase:
    def __init__(self, settings: Settings) -> None:
        self._engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def close(self) -> None:
        await self._engine.dispose()
