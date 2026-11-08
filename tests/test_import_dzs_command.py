import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from dzs_workbooks import DzsFiles

from FOIHireloom.commands.import_dzs import DzsImportCommand, main
from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.dzs import DzsImportResultDTO, DzsSeriesDTO, DzsSourceDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services.dependency import DependencyService

SERIES = DzsSeriesDTO(source="t1", values=504, provisional=378, missing=0, first_period=date(2026, 7, 1),
                      last_period=date(2026, 9, 1))


class FakeDzsImportService:
    def __init__(self, status: str = "succeeded", error: Exception | None = None) -> None:
        self.calls: list[tuple[str, DzsSourceDTO, DzsSourceDTO]] = []
        self.status = status
        self.error = error

    async def validate_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        self.calls.append(("validate", t1, workbook))
        return DzsImportResultDTO(status="validated" if self.status == "succeeded" else self.status, dry_run=True,
                                  series=(SERIES,))

    async def import_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        self.calls.append(("import", t1, workbook))
        if self.error is not None:
            raise self.error
        return DzsImportResultDTO(import_id=7, status=self.status, series=(SERIES,), values_inserted=504,
                                  values_updated=0, values_unchanged=0)


def dependencies(service: FakeDzsImportService, databases: list[bool]):
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def dzs_import_service(self, *, with_database: bool = True):
            databases.append(with_database)
            yield service

    return patch("FOIHireloom.commands.import_dzs.DependencyService", FakeDependencyService)


class ImportDzsCommandTests(unittest.TestCase):
    def run_main(self, service: FakeDzsImportService, *argv: str) -> tuple[int, str, str, list[bool]]:
        out, err, databases = io.StringIO(), io.StringIO(), []
        code = 0
        with dependencies(service, databases), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.dict("os.environ", {"DZS_T1_URL": "https://example.com/t1.xlsx",
                                          "DZS_WORKBOOK_URL": "https://example.com/workbook.xlsx"}):
            try:
                main(list(argv))
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue(), databases

    def test_downloads_the_configured_urls_and_prints_a_json_summary(self) -> None:
        service = FakeDzsImportService()
        code, out, _, databases = self.run_main(service)
        self.assertEqual((code, databases), (0, [True]))
        self.assertEqual(service.calls, [("import", DzsSourceDTO(location=Settings().DZS_T1_URL),
                                          DzsSourceDTO(location=Settings().DZS_WORKBOOK_URL))])
        summary = json.loads(out)
        self.assertEqual((summary["import_id"], summary["status"], summary["values_inserted"]), (7, "succeeded", 504))
        self.assertEqual(summary["series"][0]["first_period"], "2026-07-01")

    def test_local_files_and_dry_run_skip_the_database(self) -> None:
        service = FakeDzsImportService()
        code, out, _, databases = self.run_main(service, "--dry-run", "--t1-file", "raw/t1.xlsx",
                                                "--workbook-file", "raw/workbook.xlsx")
        self.assertEqual((code, databases, json.loads(out)["status"]), (0, [False], "validated"))
        self.assertEqual(service.calls, [("validate", DzsSourceDTO(location="raw/t1.xlsx", local=True),
                                          DzsSourceDTO(location="raw/workbook.xlsx", local=True))])
        self.run_main(service, "--t1-file", "raw/t1.xlsx")
        self.assertEqual(service.calls[-1][1:], (DzsSourceDTO(location="raw/t1.xlsx", local=True),
                                                 DzsSourceDTO(location=Settings().DZS_WORKBOOK_URL)))

    def test_exits_1_when_the_import_fails_is_rejected_or_the_database_fails(self) -> None:
        for status in ("failed", "rejected"):
            with self.subTest(status=status):
                code, out, _, _ = self.run_main(FakeDzsImportService(status))
                self.assertEqual((code, json.loads(out)["status"]), (1, status))
                self.assertEqual(self.run_main(FakeDzsImportService(status), "--dry-run")[0], 1)
        code, out, err, _ = self.run_main(FakeDzsImportService(error=PersistenceError("db down")))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)
        code, _, err, _ = self.run_main(FakeDzsImportService(error=ValueError("DZS file URL must be an HTTP(S) URL.")))
        self.assertEqual(code, 1)
        self.assertIn("DZS import failed: DZS file URL must be an HTTP(S) URL.", err)


class DzsImportWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_validates_local_files_without_a_database_engine(self) -> None:
        files = DzsFiles()
        with tempfile.TemporaryDirectory() as directory, patch(
            "FOIHireloom.services.dependency.PostgresDatabase",
            side_effect=AssertionError("A dry run must not create a database engine"),
        ), patch.dict("os.environ", {"DZS_MAX_BYTES": "100000"}):
            t1, workbook = Path(directory) / "t1.xlsx", Path(directory) / "workbook.xlsx"
            t1.write_bytes(files.t1_bytes())
            workbook.write_bytes(files.workbook_bytes())
            settings = Settings()
            command = DzsImportCommand(settings, DependencyService(settings).dzs_import_service)
            summary = await command.run(t1, workbook, dry_run=True)
        self.assertEqual((summary["status"], summary["errors"]), ("validated", []))
        self.assertEqual([file["role"] for file in summary["files"]], ["t1", "workbook"])
        self.assertEqual(summary["series"][2]["last_period"], "2026-09-01")
