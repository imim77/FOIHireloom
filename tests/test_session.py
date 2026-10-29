import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from FOIHireloom.db.database import close_database
from FOIHireloom.db.session import AsyncDBContextManager


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        database_path = Path(self.directory.name) / "sessions.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.factory_patch = patch(
            "FOIHireloom.db.session.async_session", self.factory
        )
        self.factory_patch.start()
        async with self.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE records (id INTEGER PRIMARY KEY)"))

    async def asyncTearDown(self) -> None:
        self.factory_patch.stop()
        await self.engine.dispose()
        self.directory.cleanup()

    async def count_records(self) -> int:
        async with AsyncDBContextManager() as session:
            return await session.scalar(text("SELECT COUNT(*) FROM records"))

    async def test_explicit_commit_persists_changes(self) -> None:
        async with AsyncDBContextManager() as session:
            await session.execute(text("INSERT INTO records (id) VALUES (1)"))
            await session.commit()

        self.assertEqual(await self.count_records(), 1)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_normal_exit_rolls_back_uncommitted_changes(self) -> None:
        async with AsyncDBContextManager() as session:
            await session.execute(text("INSERT INTO records (id) VALUES (1)"))

        self.assertEqual(await self.count_records(), 0)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_exception_propagates_and_releases_transaction(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "import failed"):
            async with AsyncDBContextManager() as session:
                await session.execute(text("INSERT INTO records (id) VALUES (1)"))
                raise RuntimeError("import failed")

        self.assertEqual(await self.count_records(), 0)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_concurrent_contexts_use_independent_sessions(self) -> None:
        async def read_record_count() -> tuple[int, object]:
            async with AsyncDBContextManager() as session:
                count = await session.scalar(text("SELECT COUNT(*) FROM records"))
                return count, session

        first, second = await asyncio.gather(read_record_count(), read_record_count())

        self.assertEqual(first[0], 0)
        self.assertEqual(second[0], 0)
        self.assertIsNot(first[1], second[1])
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_dispose_closes_idle_connections_and_allows_reconnection(self) -> None:
        self.assertEqual(await self.count_records(), 0)

        with patch("FOIHireloom.db.database.engine", self.engine):
            await close_database()

        self.assertEqual(self.engine.pool.checkedin(), 0)
        self.assertEqual(await self.count_records(), 0)
