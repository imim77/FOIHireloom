from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, DzsIndicatorValue
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.dzs import DzsFileDTO, DzsImportOutcomeDTO, DzsValueChangeDTO, DzsValueDTO
from FOIHireloom.exceptions import NotFoundError

FETCHED = datetime(2026, 11, 2, 11, 22, 31, tzinfo=timezone.utc)


def value(county_iso: str | None = "HR-05", **fields) -> DzsValueDTO:
    defaults = dict(county_iso=county_iso, indicator="unemployment_rate", period=date(2026, 9, 1), sex="total",
                    value=Decimal("2.3"), is_provisional=True, source="t1")
    return DzsValueDTO(**defaults | fields)


class DzsRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.session.add_all([
            County(code="varazdinska", iso_code="HR-05", name="Varaždinska županija"),
            County(code="medimurska", iso_code="HR-20", name="Međimurska županija"),
        ])
        await self.session.commit()
        self.factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))

    async def stored(self) -> list[DzsIndicatorValue]:
        async with SessionManager(self.engine).session() as reader:
            return list(await reader.scalars(select(DzsIndicatorValue).order_by(DzsIndicatorValue.id)))

    async def test_create_list_and_update_values(self) -> None:
        async with self.factory() as work:
            first = await work.dzs_imports.start()
            now = await work.transaction_time()
            await work.dzs_indicator_values.create_many([
                value(),
                value("HR-20", indicator="unemployed", value=Decimal(1459), is_provisional=False),
                value(sex="men", value=None, missing_reason="not_available", source="workbook_9_4_14"),
            ], first, now)
            await work.commit()
        async with self.factory() as work:
            snapshots = {snapshot.key: snapshot for snapshot in await work.dzs_indicator_values.list_snapshots()}
        self.assertEqual(set(snapshots), {
            ("HR-05", "unemployment_rate", date(2026, 9, 1), "total"),
            ("HR-20", "unemployed", date(2026, 9, 1), "total"),
            ("HR-05", "unemployment_rate", date(2026, 9, 1), "men"),
        })
        rate = snapshots[("HR-05", "unemployment_rate", date(2026, 9, 1), "total")]
        self.assertEqual((rate.value, rate.is_provisional, rate.source), (Decimal("2.3"), True, "t1"))
        men = snapshots[("HR-05", "unemployment_rate", date(2026, 9, 1), "men")]
        self.assertEqual((men.value, men.missing_reason), (None, "not_available"))

        async with self.factory() as work:
            second = await work.dzs_imports.start()
            later = await work.transaction_time()
            await work.dzs_indicator_values.update_many([
                DzsValueChangeDTO(id=rate.id, value=value(value=Decimal("2.4")), revised=True),
                DzsValueChangeDTO(id=men.id, value=value(sex="men", value=None, missing_reason="not_available",
                                                         source="workbook_9_4_14", is_provisional=False),
                                  revised=False),
            ], second, later)
            await work.commit()
        rows = {row.id: row for row in await self.stored()}
        self.assertEqual((rows[rate.id].value, rows[rate.id].revised_at, rows[rate.id].import_id),
                         (Decimal("2.4"), later, second))
        self.assertEqual((rows[men.id].is_provisional, rows[men.id].revised_at, rows[men.id].updated_at),
                         (False, None, later))
        untouched = next(row for row in rows.values() if row.indicator == "unemployed")
        self.assertEqual((untouched.import_id, untouched.updated_at), (first, now))

    async def test_values_without_a_stored_county_are_rejected_before_writing(self) -> None:
        for county_iso in ("HR-01", None):
            with self.subTest(county_iso=county_iso):
                async with self.factory() as work:
                    run = await work.dzs_imports.start()
                    with self.assertRaisesRegex(ValueError, "unknown ISO codes"):
                        await work.dzs_indicator_values.create_many(
                            [value(), value(county_iso, period=date(2026, 8, 1))], run, await work.transaction_time()
                        )
        self.assertEqual(await self.stored(), [])

    async def test_finish_records_outcome_and_files(self) -> None:
        file = DzsFileDTO(role="workbook", location="docs/raw/workbook.xlsx", sheets=("9.4.13.", "9.4.14."),
                          sha256="0" * 64, size_bytes=10, fetched_at=FETCHED)
        async with self.factory() as work:
            run_id = await work.dzs_imports.start()
            await work.dzs_imports.finish(run_id, DzsImportOutcomeDTO(
                status="rejected", error_summary="T1: title not found.", files=(file,),
            ), await work.transaction_time())
            await work.commit()
        async with self.factory() as work:
            run = await work.dzs_imports.get_by_id(run_id)
            self.assertEqual((run.status, run.error_summary, run.values_inserted), ("rejected", "T1: title not found.", None))
            self.assertEqual([(f.role, f.location, f.sheets, f.fetched_at) for f in run.files],
                             [("workbook", "docs/raw/workbook.xlsx", ["9.4.13.", "9.4.14."], FETCHED)])
            self.assertIsNone(await work.dzs_imports.get_by_id(run_id + 1))
            with self.assertRaises(NotFoundError):
                await work.dzs_imports.finish(run_id + 1, DzsImportOutcomeDTO(status="failed", error_summary="x"),
                                              await work.transaction_time())
