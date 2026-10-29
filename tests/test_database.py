import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import engine
from FOIHireloom.db.session import async_session


class DatabaseConfigurationTests(unittest.TestCase):
    def test_engine_uses_asyncpg_and_shared_session_factory(self) -> None:
        self.assertEqual(engine.dialect.name, "postgresql")
        self.assertEqual(engine.dialect.driver, "asyncpg")
        self.assertTrue(engine.dialect.is_async)
        self.assertIs(async_session.kw["bind"], engine)
        self.assertFalse(async_session.kw["expire_on_commit"])

    def test_environment_overrides_dotenv_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "DATABASE_URL=postgresql+asyncpg://file/db\n"
                "DATABASE_POOL_SIZE=8\n"
                "DATABASE_MAX_OVERFLOW=5\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "DATABASE_URL": "postgresql+asyncpg://example/db",
                    "DATABASE_POOL_SIZE": "3",
                    "DATABASE_MAX_OVERFLOW": "2",
                },
            ):
                settings = Settings(_env_file=env_file)

        self.assertEqual(settings.DATABASE_URL, "postgresql+asyncpg://example/db")
        self.assertEqual(settings.DATABASE_POOL_SIZE, 3)
        self.assertEqual(settings.DATABASE_MAX_OVERFLOW, 2)

    def test_dotenv_loads_database_settings_and_ignores_unrelated_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "DATABASE_URL=postgresql+asyncpg://file/db\n"
                "DATABASE_POOL_SIZE=8\n"
                "UNRELATED_SETTING=ignored\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(_env_file=env_file)

        self.assertEqual(settings.DATABASE_URL, "postgresql+asyncpg://file/db")
        self.assertEqual(settings.DATABASE_POOL_SIZE, 8)

    def test_pool_limits_reject_invalid_values(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, DATABASE_POOL_SIZE=0)
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, DATABASE_MAX_OVERFLOW=-1)
