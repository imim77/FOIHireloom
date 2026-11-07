"""PostgreSQL regressions; set TEST_DATABASE_URL to a migrated local database.

Each test rolls back its outer transaction, including service commits.
"""

import os
import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from FOIHireloom.db.models import Base, DzsIndicatorValue, Job, SourceFeed
from FOIHireloom.db.uow.sqla import SqlAlchemyUnitOfWork
from FOIHireloom.dto.dzs import DzsReleaseDTO, DzsValueDTO
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_sync import FilledCategoryDTO
from FOIHireloom.dto.job_search import JobCursorDTO, JobSearchCriteriaDTO
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.dzs_import import DzsImportService
from FOIHireloom.services.concrete.dzs_release_parser import DzsReleaseParser
from FOIHireloom.services.concrete.job_sync import CountyFeedSync


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for PostgreSQL integration tests")
class DatabaseSimplificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        self.connection = await self.engine.connect()
        self.transaction = await self.connection.begin()
        connection = self.connection

        class BoundSessions:
            def session(self) -> AsyncSession:
                return AsyncSession(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")

        self.work = lambda: SqlAlchemyUnitOfWork(BoundSessions())
        catalog = CroatianCountyCatalog()
        self.service = DzsImportService(None, DzsReleaseParser(catalog), self.work, catalog)

    async def asyncTearDown(self) -> None:
        await self.transaction.rollback()
        await self.connection.close()
        await self.engine.dispose()

    async def apply(self, value: DzsValueDTO):
        async with self.work() as work:
            import_id = await work.dzs_imports.start()
            await work.commit()
        result = await self.service._apply(import_id, DzsReleaseDTO(values=(value,), series=()), [])
        row = (await self.connection.execute(select(*(c.label(c.key) for c in DzsIndicatorValue.__table__.columns)).where(
            DzsIndicatorValue.period == value.period,
            DzsIndicatorValue.indicator == value.indicator,
            DzsIndicatorValue.sex == value.sex,
            DzsIndicatorValue.county_id == self.county_id,
        ))).mappings().one()
        return result, row

    async def test_import_preserves_identity_and_counts_for_value_and_metadata_changes(self) -> None:
        async with self.work() as work:
            county = (await work.counties.list_all())[0]
        self.county_id = county.id
        value = DzsValueDTO(county_iso=county.iso_code, indicator="unemployment_rate", period=date(1900, 1, 1),
                            sex="total", value=Decimal("5.0"), is_provisional=False, source="t1")
        created, original = await self.apply(value)
        self.assertEqual((created.values_inserted, created.values_updated, created.values_unchanged), (1, 0, 0))
        unchanged, row = await self.apply(value)
        self.assertEqual((unchanged.values_inserted, unchanged.values_updated, unchanged.values_unchanged), (0, 0, 1))
        self.assertEqual(row["import_id"], original["import_id"])
        for changed in (value.model_copy(update={"value": Decimal("6.0")}),
                        value.model_copy(update={"value": Decimal("6.0"), "is_provisional": True}),
                        value.model_copy(update={"value": None, "missing_reason": "not_available"})):
            with self.subTest(value=changed):
                result, row = await self.apply(changed)
                self.assertEqual((result.values_inserted, result.values_updated, result.values_unchanged), (0, 1, 0))
                self.assertEqual(row["id"], original["id"])
                self.assertEqual(row["import_id"], result.import_id)
                self.assertEqual(row["value"], changed.value)
                self.assertEqual(row["is_provisional"], changed.is_provisional)
                self.assertEqual(row["missing_reason"], changed.missing_reason)

    async def test_hzz_sync_inserts_updates_and_matches_by_source_id(self) -> None:
        job = ParsedJobDTO(source_job_id="cleanup-regression", canonical_url="https://example.com/cleanup-regression",
                           title="Test job", description_text=None, published_on=date(2026, 11, 7), deadline_on=None,
                           category=None, location_text=None, municipality=None, quality_flags=(), content_hash="first")
        async with self.work() as work:
            now = await work.transaction_time()
            linked = await CountyFeedSync.upsert_jobs(work, (job,), now)
            self.assertEqual((linked.added, linked.changed, linked.unchanged), (1, 0, 0))
            original_id = linked.job_ids[job.source_job_id]
            linked = await CountyFeedSync.upsert_jobs(work, (job,), now)
            self.assertEqual((linked.added, linked.changed, linked.unchanged), (0, 0, 1))
            replacement = job.model_copy(update={"title": "Changed job", "content_hash": "second"})
            linked = await CountyFeedSync.upsert_jobs(work, (replacement,), now)
            self.assertEqual((linked.added, linked.changed, linked.unchanged), (0, 1, 0))
            self.assertEqual(linked.job_ids[job.source_job_id], original_id)
            snapshots = await work.jobs.list_snapshots((job.source_job_id,))
            self.assertEqual([(s.id, s.content_hash) for s in snapshots], [(original_id, "second")])

    async def test_hzz_identity_remains_unique_and_eu_scope_is_rejected(self) -> None:
        jobs = (await self.connection.execute(select(Job.id, Job.source_job_id, Job.canonical_url)
                                             .order_by(Job.id).limit(2))).all()
        self.assertEqual(len(jobs), 2)
        for column in ("source_job_id", "canonical_url"):
            with self.subTest(column=column):
                async with AsyncSession(self.connection, join_transaction_mode="create_savepoint") as session:
                    with self.assertRaises(IntegrityError):
                        await session.execute(update(Job).where(Job.id == jobs[1].id)
                                              .values(**{column: getattr(jobs[0], column)}))
                    await session.rollback()
        feed_id = await self.connection.scalar(select(SourceFeed.id).where(SourceFeed.scope == "occupation").limit(1))
        self.assertIsNotNone(feed_id)
        async with AsyncSession(self.connection, join_transaction_mode="create_savepoint") as session:
            with self.assertRaises(IntegrityError):
                await session.execute(update(SourceFeed).where(SourceFeed.id == feed_id).values(scope="eu"))
            await session.rollback()

    async def test_category_pagination_keeps_unknown_deadlines_and_prefers_page_deadline(self) -> None:
        today = date(2026, 11, 7)
        past, future = date(2026, 11, 6), date(2026, 11, 8)
        cases = (("unknown", None, None), ("feed", future, None),
                 ("expired-page", future, past), ("open-page", past, future))
        async with self.work() as work:
            now = await work.transaction_time()
            jobs = tuple(ParsedJobDTO(
                source_job_id=f"index-regression-{name}", canonical_url=f"https://example.com/index-{name}",
                title=name, description_text=None, published_on=today, deadline_on=feed_deadline,
                category="INDEX REGRESSION", location_text=None, municipality=None, quality_flags=(), content_hash=name,
            ) for name, feed_deadline, _ in cases)
            ids = await work.jobs.create_many(jobs, now)
            feed_id = await self.connection.scalar(select(SourceFeed.id).where(SourceFeed.scope == "county").limit(1))
            await work.job_feed_memberships.create_many(feed_id, list(ids.values()), now)
            # The page's deadline may override either a future or an expired feed deadline.
            for name, _, page_deadline in cases:
                await self.connection.execute(update(Job).where(Job.id == ids[f"index-regression-{name}"])
                                              .values(page_valid_until=page_deadline))
            criteria = JobSearchCriteriaDTO(category="index regression", open_on=today, limit=2)
            first = await work.jobs.search(criteria)
            last = first[-1].job
            second = await work.jobs.search(criteria.model_copy(update={
                "after": JobCursorDTO(id=last.id, published_on=last.published_on),
            }))
            found = [hit.job.id for hit in (*first, *second)]
            expected = [ids[f"index-regression-{name}"] for name in ("open-page", "feed", "unknown")]
            self.assertEqual(found, expected)

    async def test_physical_catalog_uses_croatian_names(self) -> None:
        tables = set((await self.connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version'"
        ))).scalars())
        self.assertEqual(tables, {"zupanije", "oglasi", "izvorni_kanali", "pripadnosti_oglasa_kanalima",
                                  "sinkronizacije", "uvozi_dzs", "datoteke_uvoza_dzs", "vrijednosti_pokazatelja_dzs"})
        for table in Base.metadata.sorted_tables:
            stored = set((await self.connection.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:name"
            ), {"name": table.name})).scalars())
            self.assertEqual(stored, {column.name for column in table.columns})

    async def test_core_category_update_and_generated_search_work_after_renaming(self) -> None:
        job = ParsedJobDTO(source_job_id="croatian-schema-regression",
                           canonical_url="https://example.com/croatian-schema-regression", title="Python developer",
                           description_text=None, published_on=date(2026, 11, 7), deadline_on=None,
                           category=None, location_text=None, municipality=None, quality_flags=(), content_hash="test")
        async with self.work() as work:
            now = await work.transaction_time()
            job_id = (await work.jobs.create_many((job,), now))[job.source_job_id]
            feed_id = await self.connection.scalar(select(SourceFeed.id).where(SourceFeed.scope == "occupation").limit(1))
            county_feed = await self.connection.scalar(select(SourceFeed.id).where(SourceFeed.scope == "county").limit(1))
            await work.job_feed_memberships.create_many(county_feed, (job_id,), now)
            await work.jobs.set_feed_categories({job_id: FilledCategoryDTO(category="SCHEMA REGRESSION", feed_id=feed_id)})
            found = await work.jobs.search(JobSearchCriteriaDTO(
                terms=("python",), skills=("python",), category="schema regression", limit=10,
            ))
            self.assertEqual([hit.job.id for hit in found], [job_id])
            self.assertEqual(found[0].job.category_feed_id, feed_id)
            self.assertEqual(found[0].job.category_source, "feed")
            self.assertIn("python", found[0].job.skills)
