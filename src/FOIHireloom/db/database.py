from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from FOIHireloom.config.settings import Settings


class PostgresDatabase:
    def __init__(self, settings: Settings) -> None:
        self._engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=30,
            pool_recycle=1800,
            pool_use_lifo=True,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def close(self) -> None:
        await self._engine.dispose()
