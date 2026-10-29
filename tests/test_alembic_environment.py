import ast
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from FOIHireloom.db.models import Base


class AlembicEnvironmentTests(unittest.TestCase):
    config_path = (
        Path(__file__).resolve().parents[1]
        / "src/FOIHireloom/db/alembic/alembic.ini"
    )

    def test_script_location_is_relative_to_configuration_file(self) -> None:
        config = Config(str(self.config_path))
        scripts = ScriptDirectory.from_config(config)
        self.assertEqual(Path(scripts.dir).resolve(), self.config_path.parent)

    def test_revision_template_generates_valid_typed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / "versions").mkdir()
            shutil.copy2(self.config_path.parent / "script.py.mako", destination)
            config = Config()
            config.set_main_option("script_location", str(destination))
            revision = command.revision(config, message="test template")
            source = Path(revision.path).read_text(encoding="utf-8")
            tree = ast.parse(source)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(functions), {"upgrade", "downgrade"})
        self.assertTrue(all(node.returns is not None for node in functions.values()))

    def test_offline_mode_does_not_connect_or_interpolate_url_password(self) -> None:
        output = io.StringIO()
        config = Config(str(self.config_path), output_buffer=output)
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql+asyncpg://example:p%25ss@invalid.example/offline"
        }), patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            side_effect=AssertionError("Offline migrations must not create an engine"),
        ):
            command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        self.assertNotIn("p%25ss", sql)

    def test_offline_upgrade_contains_all_model_tables(self) -> None:
        output = io.StringIO()
        config = Config(str(self.config_path), output_buffer=output)
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://invalid.example/offline"}):
            command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        for table_name in Base.metadata.tables:
            self.assertIn(f"CREATE TABLE {table_name}", sql)
        self.assertIn("JSONB", sql)
        self.assertIn("TEXT[]", sql)

    def test_offline_downgrade_has_explicit_revision_range(self) -> None:
        output = io.StringIO()
        config = Config(str(self.config_path), output_buffer=output)
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://invalid.example/offline"}):
            command.downgrade(config, "head:base", sql=True)
        sql = output.getvalue()
        self.assertLess(sql.index("DROP TABLE job_feed_memberships"), sql.index("DROP TABLE jobs"))
        self.assertLess(sql.index("DROP TABLE jobs"), sql.index("DROP TABLE employers"))
