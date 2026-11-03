import hashlib
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import delete, func, select

from dzs_workbooks import DzsFiles
from model_test_case import ModelTestCase

from FOIHireloom.dao.concrete.sqla_dzs_import import SqlAlchemyDzsImportRepository
from FOIHireloom.dao.concrete.sqla_dzs_indicator_value import SqlAlchemyDzsIndicatorValueRepository
from FOIHireloom.db.models import County, DzsImport, DzsIndicatorValue
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.dzs import DzsSourceDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.integrations.concrete.dzs import DzsClient
from FOIHireloom.services import CroatianCountyCatalog, DzsImportService, DzsReleaseParser

T1_URL = "https://podaci.dzs.hr/media/ulbjlyex/rad-2026-2-6_3_tablice-hr.xlsx"
WORKBOOK_URL = "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx"
T1, WORKBOOK = DzsSourceDTO(location=T1_URL), DzsSourceDTO(location=WORKBOOK_URL)
# 21 counties: T1 504; 9.4.13 8 months x 2 sexes; 9.4.14 8 months x 3 sexes plus the T1 months for men.
VALUES = 504 + 21 * 2 * 8 + 21 * (3 * 8 + 3)
JULY = date(2026, 7, 1)


class DzsImportTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        catalog = CroatianCountyCatalog()
        self.session.add_all([County(**county.model_dump()) for county in catalog.definitions])
        await self.session.commit()
        self.files = DzsFiles()
        self.status = {T1_URL: 200, WORKBOOK_URL: 200}
        self.requests: list[httpx.Request] = []
        # The bytes last served per URL; each save embeds timestamps, so a rebuilt file can differ.
        self.served: dict[str, bytes] = {}
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))
        self.addAsyncCleanup(self.http.aclose)
        self.sessions = SessionManager(self.engine)
        self.parser = DzsReleaseParser(catalog)
        self.service = DzsImportService(DzsClient(self.http), self.parser, SqlAlchemyUnitOfWorkFactory(self.sessions),
                                        catalog)

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.assertEqual(self.engine.pool.checkedout(), 0, "Downloads must not hold a database connection")
        url = str(request.url)
        if self.status[url] != 200:
            return httpx.Response(self.status[url])
        content = self.files.t1_bytes() if url == T1_URL else self.files.workbook_bytes()
        self.served[url] = content
        return httpx.Response(200, content=content, headers={
            "ETag": f'"{hashlib.sha256(content).hexdigest()[:8]}"', "Last-Modified": "Wed, 28 Oct 2026 10:00:47 GMT",
        })

    async def stored(self) -> dict[tuple, DzsIndicatorValue]:
        async with self.sessions.session() as reader:
            rows = await reader.execute(select(County.iso_code, DzsIndicatorValue).join(County))
            return {(iso, row.indicator, row.period, row.sex): row for iso, row in rows.all()}

    async def runs(self) -> list[DzsImport]:
        async with self.sessions.session() as reader:
            repository = SqlAlchemyDzsImportRepository(reader)
            ids = (await reader.scalars(select(DzsImport.id).order_by(DzsImport.id))).all()
            return [await repository.get_by_id(run_id) for run_id in ids]

    async def test_first_import_stores_every_county_value_with_provenance(self) -> None:
        result = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual((result.status, result.values_inserted, result.values_updated, result.values_unchanged),
                         ("succeeded", VALUES, 0, 0))
        self.assertEqual([request.url for request in self.requests], [T1_URL, WORKBOOK_URL])
        stored = await self.stored()
        self.assertEqual(len(stored), VALUES)
        unemployed = stored[("HR-18", "unemployed", JULY, "total")]
        self.assertEqual((unemployed.value, unemployed.is_provisional, unemployed.source, unemployed.import_id),
                         (Decimal(self.files.get_t1("Istarska", "total", "unemployed", 7)), False, "t1", result.import_id))
        self.assertIsNone(unemployed.revised_at)
        men = stored[("HR-18", "unemployment_rate", JULY, "men")]
        self.assertEqual((men.source, men.is_provisional), ("workbook_9_4_14", True))
        self.assertFalse(stored[("HR-18", "active_population", date(2025, 12, 1), "women")].is_provisional)
        [run] = await self.runs()
        self.assertEqual((run.id, run.status, run.values_inserted, run.error_summary), (result.import_id, "succeeded", VALUES, None))
        self.assertEqual([(f.role, f.location, f.sheets) for f in run.files],
                         [("t1", T1_URL, ["T1"]), ("workbook", WORKBOOK_URL, ["9.4.13.", "9.4.14."])])
        self.assertEqual([(f.sha256, f.size_bytes) for f in run.files],
                         [(hashlib.sha256(self.served[url]).hexdigest(), len(self.served[url]))
                          for url in (T1_URL, WORKBOOK_URL)])
        self.assertEqual(run.files[0].source_last_modified_at, datetime(2026, 10, 28, 10, 0, 47, tzinfo=timezone.utc))
        self.assertEqual(run.files[0].etag, result.files[0].etag)
        self.assertEqual([s.source for s in result.series], ["t1", "workbook_9_4_13", "workbook_9_4_14"])

    async def test_identical_reimport_changes_nothing(self) -> None:
        first = await self.service.import_release(T1, WORKBOOK)
        before = {key: (row.id, row.updated_at) for key, row in (await self.stored()).items()}
        second = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual((second.status, second.values_inserted, second.values_updated, second.values_unchanged),
                         ("succeeded", 0, 0, VALUES))
        stored = await self.stored()
        self.assertEqual({key: (row.id, row.updated_at) for key, row in stored.items()}, before)
        self.assertEqual({row.import_id for row in stored.values()}, {first.import_id})
        self.assertEqual([run.status for run in await self.runs()], ["succeeded", "succeeded"])

    async def test_revised_values_update_their_rows_and_record_the_revision(self) -> None:
        first = await self.service.import_release(T1, WORKBOOK)
        unemployed = self.files.get_t1("Istarska", "total", "unemployed", 7)
        employed = self.files.get_t1("Istarska", "total", "employed", 7)
        croatia = self.files.get_t1("Republika Hrvatska", "total", "unemployed", 7)
        self.files.set_t1("Istarska", "total", "unemployed", 7, unemployed + 5)
        self.files.set_t1("Istarska", "total", "employed", 7, employed - 5)
        self.files.set_t1("Republika Hrvatska", "total", "unemployed", 7, croatia + 5)
        self.files.set_t1("Republika Hrvatska", "total", "employed", 7,
                          self.files.get_t1("Republika Hrvatska", "total", "employed", 7) - 5)
        self.files.set_series("9.4.14.", "Istarska", 2026, 1, "men", "…")
        second = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual((second.status, second.values_inserted, second.values_updated, second.values_unchanged),
                         ("succeeded", 0, 3, VALUES - 3))
        stored = await self.stored()
        revised = {key: row for key, row in stored.items() if row.revised_at is not None}
        self.assertEqual(set(revised), {
            ("HR-18", "unemployed", JULY, "total"), ("HR-18", "employed", JULY, "total"),
            ("HR-18", "unemployment_rate", date(2026, 1, 1), "men"),
        })
        self.assertEqual(revised[("HR-18", "unemployed", JULY, "total")].value, Decimal(unemployed + 5))
        missing = revised[("HR-18", "unemployment_rate", date(2026, 1, 1), "men")]
        self.assertEqual((missing.value, missing.missing_reason), (None, "not_available"))
        self.assertEqual({row.import_id for row in revised.values()}, {second.import_id})
        self.assertEqual({row.revised_at for row in revised.values()}, {row.updated_at for row in revised.values()})
        self.assertEqual({row.import_id for key, row in stored.items() if key not in revised}, {first.import_id})

    async def test_a_new_provisional_status_updates_without_a_revision(self) -> None:
        await self.service.import_release(T1, WORKBOOK)
        self.files.sheets["9.4.13."][-3] = ["1) Podaci od 2025. privremeni su."]
        result = await self.service.import_release(T1, WORKBOOK)
        # November and December 2025, total and women, in 21 counties.
        self.assertEqual((result.values_updated, result.values_unchanged), (84, VALUES - 84))
        stored = await self.stored()
        row = stored[("HR-05", "active_population", date(2025, 11, 1), "total")]
        self.assertEqual((row.is_provisional, row.revised_at, row.import_id), (True, None, result.import_id))
        self.assertGreater(row.updated_at, row.created_at)

    async def test_rejected_files_keep_previous_values_and_record_the_problems(self) -> None:
        first = await self.service.import_release(T1, WORKBOOK)
        before = {key: (row.value, row.import_id) for key, row in (await self.stored()).items()}
        self.files.set_series("9.4.13.", "Grad Zagreb", 2026, 7, "total", 1)
        self.files.set_series("9.4.13.", "Zadarska", 2026, 8, "women", 1)
        result = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(len(result.errors), 2)
        self.assertIn("T1 and 9.4.13. differ for Zadarska županija 2026-08 women", result.errors[0])
        self.assertIn("T1 and 9.4.13. differ for Grad Zagreb 2026-07 total", result.errors[1])
        self.assertEqual({key: (row.value, row.import_id) for key, row in (await self.stored()).items()}, before)
        runs = await self.runs()
        self.assertEqual([(run.status, run.values_inserted) for run in runs], [("succeeded", VALUES), ("rejected", None)])
        self.assertEqual(runs[1].error_summary, "\n".join(result.errors))
        self.assertEqual(len(runs[1].files), 2)
        self.assertEqual(first.import_id + 1, result.import_id)

    async def test_failure_while_applying_rolls_back_every_write(self) -> None:
        with patch.object(SqlAlchemyDzsIndicatorValueRepository, "update_many",
                          side_effect=PersistenceError("connection lost")):
            failed = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual((failed.status, failed.errors), ("failed", ("connection lost",)))
        self.assertEqual(await self.stored(), {})

        await self.service.import_release(T1, WORKBOOK)
        before = {key: (row.value, row.import_id, row.updated_at) for key, row in (await self.stored()).items()}
        self.files.set_series("9.4.14.", "Istarska", 2026, 1, "men", 0)
        with patch.object(SqlAlchemyDzsIndicatorValueRepository, "update_many",
                          side_effect=PersistenceError("connection lost")):
            self.assertEqual((await self.service.import_release(T1, WORKBOOK)).status, "failed")
        self.assertEqual({key: (row.value, row.import_id, row.updated_at) for key, row in (await self.stored()).items()},
                         before)
        runs = await self.runs()
        self.assertEqual([run.status for run in runs], ["failed", "succeeded", "failed"])
        self.assertEqual((runs[2].error_summary, len(runs[2].files)), ("connection lost", 2))

    async def test_download_errors_and_missing_counties_fail_without_writing(self) -> None:
        self.status[WORKBOOK_URL] = 503
        result = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual((result.status, result.errors), ("failed", ("DZS returned HTTP 503.",)))
        self.assertEqual([file.role for file in result.files], ["t1"])

        self.status[WORKBOOK_URL] = 200
        await self.session.execute(delete(County).where(County.iso_code.in_(["HR-09", "HR-20"])))
        await self.session.commit()
        result = await self.service.import_release(T1, WORKBOOK)
        self.assertEqual(result.errors, ("Counties HR-09, HR-20 are not stored; run foihireloom-register-sources first.",))
        self.assertEqual(await self.stored(), {})
        self.assertEqual([(run.status, len(run.files)) for run in await self.runs()], [("failed", 1), ("failed", 2)])

    async def test_unexpected_errors_are_recorded_and_raised(self) -> None:
        with patch.object(self.parser, "parse", side_effect=KeyError("bug")), self.assertRaises(KeyError):
            await self.service.import_release(T1, WORKBOOK)
        [run] = await self.runs()
        self.assertEqual((run.status, run.error_summary), ("failed", "'bug'"))

    async def test_validation_reads_local_files_and_never_touches_the_database(self) -> None:
        service = DzsImportService(DzsClient(self.http), self.parser, None, CroatianCountyCatalog())
        with tempfile.TemporaryDirectory() as directory:
            t1, workbook = Path(directory) / "t1.xlsx", Path(directory) / "workbook.xlsx"
            written = self.files.t1_bytes(), self.files.workbook_bytes()
            t1.write_bytes(written[0])
            workbook.write_bytes(written[1])
            local = DzsSourceDTO(location=str(t1), local=True), DzsSourceDTO(location=str(workbook), local=True)
            result = await service.validate_release(*local)
            self.assertEqual((result.status, result.dry_run, result.import_id, result.values_inserted, result.errors),
                             ("validated", True, None, None, ()))
            self.assertEqual([(f.location, f.sha256, f.size_bytes, f.etag) for f in result.files],
                             [(str(path), hashlib.sha256(content).hexdigest(), len(content), None)
                              for path, content in zip((t1, workbook), written)])
            self.assertEqual(sum(s.values for s in result.series), VALUES)
            self.assertEqual(self.requests, [])

            workbook.write_bytes(t1.read_bytes())
            rejected = await service.validate_release(*local)
            self.assertEqual((rejected.status, rejected.errors), ("rejected", (
                "Workbook: missing sheet(s) 9.4.13., 9.4.14.; found T1, T2.",
            )))
            failed = await service.validate_release(local[0], DzsSourceDTO(location=directory + "/none.xlsx", local=True))
            self.assertEqual(failed.status, "failed")
            self.assertIn("none.xlsx", failed.errors[0])
        self.assertEqual(await self.session.scalar(select(func.count(DzsImport.id))), 0)
        with self.assertRaises(RuntimeError):
            await service.import_release(T1, WORKBOOK)

    async def test_long_problem_lists_are_shortened(self) -> None:
        for month in range(1, 10):
            for sex in ("total", "men", "women"):
                self.files.set_series("9.4.14.", "Istarska", 2026, month, sex, "x")
        result = await self.service.validate_release(T1, WORKBOOK)
        self.assertEqual(len(result.errors), 21)
        self.assertEqual(result.errors[-1], "… and 7 more problems.")
