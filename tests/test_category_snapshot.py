import contextlib
import io
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from FOIHireloom.commands.category_snapshot import main
from FOIHireloom.dto.category_snapshot import CategoryCoverageDTO, CategorySnapshotDTO
from FOIHireloom.exceptions import PersistenceError


class FixedService:
    def __init__(self, snapshot: CategorySnapshotDTO | None = None, error: Exception | None = None) -> None:
        self.snapshot, self.error = snapshot, error

    async def take(self) -> CategorySnapshotDTO:
        if self.error is not None:
            raise self.error
        return self.snapshot


def run_main(service: FixedService, *argv: str) -> tuple[int, str, str]:
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def category_snapshot_service(self):
            yield service

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("FOIHireloom.commands.category_snapshot.DependencyService", FakeDependencyService), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main(list(argv))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class CategorySnapshotCommandErrorTests(unittest.TestCase):
    def test_database_error_exits_1_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            code, out, err = run_main(FixedService(error=PersistenceError("db down")), "--out", str(path))
            self.assertFalse(path.exists())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)

    def test_unwritable_out_exits_1(self) -> None:
        empty = CategorySnapshotDTO(
            generated_at=datetime.now(UTC), denominator="", feeds=(), categories=(), jobs=(),
            coverage=CategoryCoverageDTO(listed=0, before=0, after=0, filled=0, unknown=0, conflicting=0),
        )
        with tempfile.TemporaryDirectory() as directory:
            code, out, err = run_main(FixedService(empty), "--out", str(Path(directory) / "missing" / "s.json"))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot write", err)
