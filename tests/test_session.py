import asyncio
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import PostgresDatabase
from FOIHireloom.db.session import SessionManager


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        database_path = Path(self.directory.name) / "sessions.db"
        settings = Settings(
            _env_file=None,
            DATABASE_URL=f"sqlite+aiosqlite:///{database_path}",
        )
        self.database = PostgresDatabase(settings)
        self.engine = self.database.engine
        self.sessions = SessionManager(self.engine)
        async with self.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE records (id INTEGER PRIMARY KEY)"))

    async def asyncTearDown(self) -> None:
        await self.database.close()
        self.directory.cleanup()

    async def count_records(self) -> int:
        async with self.sessions.session() as session:
            return await session.scalar(text("SELECT COUNT(*) FROM records"))

    async def test_explicit_commit_persists_changes(self) -> None:
        async with self.sessions.session() as session:
            await session.execute(text("INSERT INTO records (id) VALUES (1)"))
            await session.commit()

        self.assertEqual(await self.count_records(), 1)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_normal_exit_rolls_back_uncommitted_changes(self) -> None:
        async with self.sessions.session() as session:
            await session.execute(text("INSERT INTO records (id) VALUES (1)"))

        self.assertEqual(await self.count_records(), 0)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_exception_propagates_and_releases_transaction(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "import failed"):
            async with self.sessions.session() as session:
                await session.execute(text("INSERT INTO records (id) VALUES (1)"))
                raise RuntimeError("import failed")

        self.assertEqual(await self.count_records(), 0)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_concurrent_contexts_use_independent_sessions(self) -> None:
        async def read_record_count() -> tuple[int, object]:
            async with self.sessions.session() as session:
                count = await session.scalar(text("SELECT COUNT(*) FROM records"))
                return count, session

        first, second = await asyncio.gather(read_record_count(), read_record_count())

        self.assertEqual(first[0], 0)
        self.assertEqual(second[0], 0)
        self.assertIsNot(first[1], second[1])
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_dispose_closes_idle_connections_and_allows_reconnection(self) -> None:
        self.assertEqual(await self.count_records(), 0)

        await self.database.close()

        self.assertEqual(self.engine.pool.checkedin(), 0)
        self.assertEqual(await self.count_records(), 0)

    async def test_database_objects_keep_their_data_and_sessions_isolated(self) -> None:
        other_path = Path(self.directory.name) / "other.db"
        other_database = PostgresDatabase(
            Settings(_env_file=None, DATABASE_URL=f"sqlite+aiosqlite:///{other_path}")
        )
        other_sessions = SessionManager(other_database.engine)
        try:
            async with other_database.engine.begin() as connection:
                await connection.execute(
                    text("CREATE TABLE records (id INTEGER PRIMARY KEY)")
                )

            async with other_sessions.session() as session:
                await session.execute(text("INSERT INTO records (id) VALUES (1)"))
                await session.commit()

            self.assertEqual(await self.count_records(), 0)
            async with other_sessions.session() as session:
                self.assertEqual(
                    await session.scalar(text("SELECT COUNT(*) FROM records")), 1
                )
        finally:
            await other_database.close()
