from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, DzsImport, DzsImportFile, DzsIndicatorValue

SHA = "a" * 64


class DzsModelTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.county = County(code="varazdinska", iso_code="HR-05", name="Varaždinska županija")
        self.run = DzsImport()
        self.session.add_all([self.county, self.run])
        await self.session.flush()

    def value(self, **fields) -> DzsIndicatorValue:
        defaults = dict(county_id=self.county.id, indicator="unemployed", period=date(2026, 9, 1), sex="total",
                        value=Decimal(1721), is_provisional=False, source="t1", import_id=self.run.id)
        return DzsIndicatorValue(**defaults | fields)

    async def test_value_row_defaults_and_unique_key(self) -> None:
        stored = self.value()
        self.session.add(stored)
        await self.session.flush()
        await self.session.refresh(stored)
        self.assertEqual((stored.value, stored.missing_reason, stored.revised_at), (Decimal(1721), None, None))
        self.assertEqual(stored.created_at, stored.updated_at)
        await self.assert_rejected(self.value(value=Decimal(1)))
        for other in (dict(sex="women"), dict(period=date(2026, 8, 1)), dict(indicator="employed")):
            with self.subTest(other=other):
                self.session.add(self.value(**other))
                await self.session.flush()

    async def test_missing_value_needs_exactly_one_known_reason(self) -> None:
        for reason in ("no_occurrence", "not_available", "empty"):
            self.session.add(self.value(sex="women", period=date(2026, {"no_occurrence": 7, "not_available": 8,
                                                                       "empty": 9}[reason], 1),
                                        value=None, missing_reason=reason))
            await self.session.flush()
        await self.assert_rejected(self.value(value=None))
        await self.assert_rejected(self.value(value=Decimal(0), missing_reason="empty"))
        await self.assert_rejected(self.value(value=None, missing_reason="zero"))

    async def test_values_must_fit_their_unit_and_source(self) -> None:
        rate = dict(indicator="unemployment_rate", source="workbook_9_4_14")
        self.session.add(self.value(**rate, value=Decimal("2.3")))
        await self.session.flush()
        for fields in (
            dict(value=Decimal(-1)),
            dict(value=Decimal("1721.5")),
            dict(rate | dict(sex="men", value=Decimal("2.35"))),
            dict(rate | dict(sex="men", value=Decimal("100.1"))),
            dict(indicator="employed", source="workbook_9_4_13"),
            dict(indicator="active_population", source="workbook_9_4_14"),
            dict(source="hzz"),
            dict(sex="all"),
            dict(indicator="vacancies"),
            dict(period=date(2026, 9, 2)),
        ):
            with self.subTest(fields=fields):
                await self.assert_rejected(self.value(**fields))

    async def test_revision_time_lies_within_the_row_lifetime(self) -> None:
        later = datetime(2030, 1, 1, tzinfo=timezone.utc)
        await self.assert_rejected(self.value(revised_at=later))
        await self.assert_rejected(self.value(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
        self.session.add(self.value(revised_at=later, updated_at=later))
        await self.session.flush()

    async def test_import_status_constraints(self) -> None:
        finished = datetime.now(timezone.utc) + timedelta(minutes=1)
        for fields in (
            dict(status="done", finished_at=finished),
            dict(status="succeeded"),
            dict(status="succeeded", finished_at=finished, values_inserted=1, values_updated=0),
            dict(status="failed", finished_at=finished),
            dict(status="running", finished_at=finished),
            dict(status="rejected", finished_at=finished, error_summary="x", values_inserted=-1),
        ):
            with self.subTest(fields=fields):
                await self.assert_rejected(DzsImport(**fields))
        self.session.add_all([
            DzsImport(status="succeeded", finished_at=finished, values_inserted=1, values_updated=0, values_unchanged=0),
            DzsImport(status="rejected", finished_at=finished, error_summary="Bad title."),
        ])
        await self.session.flush()

    async def test_import_files_are_one_per_role_with_a_sha256(self) -> None:
        def file(**fields) -> DzsImportFile:
            defaults = dict(import_id=self.run.id, role="t1", location="https://podaci.dzs.hr/t1.xlsx", sheets=["T1"],
                            sha256=SHA, size_bytes=41633, fetched_at=datetime.now(timezone.utc))
            return DzsImportFile(**defaults | fields)

        self.session.add(file())
        await self.session.flush()
        for fields in (dict(), dict(role="t2"), dict(role="workbook", sha256="A" * 64), dict(role="workbook", location=" "),
                       dict(role="workbook", size_bytes=-1)):
            with self.subTest(fields=fields):
                await self.assert_rejected(file(**fields))
        self.session.add(file(role="workbook", sheets=["9.4.13.", "9.4.14."]))
        await self.session.flush()
