from sqlalchemy.ext.asyncio import create_async_engine

from FOIHireloom.config.settings import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=1800,
    pool_use_lifo=True,
)


async def close_database() -> None:
    await engine.dispose()
