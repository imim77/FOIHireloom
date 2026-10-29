import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.config import Config
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.models import Base


class MigrationEnvironment:
    def __init__(self, config: Config, settings: Settings) -> None:
        self._config = config
        self._settings = settings

    def run(self) -> None:
        if self._config.config_file_name is not None:
            fileConfig(self._config.config_file_name, disable_existing_loggers=False)

        if context.is_offline_mode():
            self._run_offline()
        elif (connection := self._config.attributes.get("connection")) is not None:
            self._run_migrations(connection)
        else:
            asyncio.run(self._run_online())

    def _run_offline(self) -> None:
        context.configure(
            url=self._settings.DATABASE_URL,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    def _run_migrations(self, connection: Connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def _run_online(self) -> None:
        engine = create_async_engine(self._settings.DATABASE_URL, poolclass=pool.NullPool)
        try:
            async with engine.connect() as connection:
                await connection.run_sync(self._run_migrations)
        finally:
            await engine.dispose()
