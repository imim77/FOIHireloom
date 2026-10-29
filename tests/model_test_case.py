import os
import unittest
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from FOIHireloom.db.models import Base


class ModelTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url = os.environ.get("TEST_DATABASE_URL")
        if not database_url:
            self.skipTest("Set TEST_DATABASE_URL to run PostgreSQL model tests")
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("TEST_DATABASE_URL must use postgresql+asyncpg")

        self.schema = f"test_models_{uuid4().hex}"
        self.admin_engine = create_async_engine(database_url)
        self.addAsyncCleanup(self.admin_engine.dispose)
        async with self.admin_engine.begin() as connection:
            await connection.execute(CreateSchema(self.schema))
        self.addAsyncCleanup(self.drop_schema)

        self.engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": self.schema}},
        )
        self.addAsyncCleanup(self.engine.dispose)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.migrate_schema)

        self.session = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.addAsyncCleanup(self.session.close)

    def migrate_schema(self, connection: Connection) -> None:
        config_path = (
            Path(__file__).resolve().parents[1]
            / "src/FOIHireloom/db/alembic/alembic.ini"
        )
        config = Config(str(config_path))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    async def drop_schema(self) -> None:
        async with self.admin_engine.begin() as connection:
            await connection.execute(DropSchema(self.schema, cascade=True))

    async def assert_rejected(self, instance: Base) -> None:
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                self.session.add(instance)
                await self.session.flush()
