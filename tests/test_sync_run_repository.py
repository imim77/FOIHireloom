from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, SourceFeed, SyncRun
from FOIHireloom.db.session import SessionManager
from FOIHireloom.persistence.impl.sqlalchemy_sync_run_repository import SqlAlchemySyncRunRepository
from FOIHireloom.persistence.sync_run_repository import SyncRunRepository


class SyncRunRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        feed = SourceFeed(
            county=County(code="zagreb", name="Grad Zagreb"),
            ckan_resource_id=uuid4(),
            label="Poslovi u Gradu Zagrebu",
            feed_url=f"https://example.com/{uuid4()}.xml",
            scope="county",
        )
        self.session.add(feed)
        await self.session.commit()
        self.feed_id, self.county_id = feed.id, feed.county_id
        self.repository: SyncRunRepository = SqlAlchemySyncRunRepository(self.session)
        self.sessions = SessionManager(self.engine)

    def run_record(self, **overrides: object) -> SyncRun:
        return SyncRun(**({"feed_id": self.feed_id} | overrides))

    async def test_add_flushes_generated_fields_without_committing(self) -> None:
        record = self.run_record()
        self.assertIsNone(await self.repository.add(record))
        self.assertIsInstance(record.id, int)
        self.assertIsNotNone(record.started_at.tzinfo)
        self.assertEqual(record.status, "running")
        for field in [
            "finished_at", "http_status", "items_seen", "items_added",
            "items_updated", "items_invalid", "error_summary",
        ]:
            self.assertIsNone(getattr(record, field), field)
        self.assertIs(await self.repository.get_by_id(record.id), record)
        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemySyncRunRepository(reader).get_by_id(record.id))

    async def test_explicit_commit_persists_record_for_another_session(self) -> None:
        record = self.run_record()
        await self.repository.add(record)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySyncRunRepository(reader)
            saved = await repository.get_by_id(record.id)
            self.assertIsNotNone(saved)
            self.assertIsNot(saved, record)
            self.assertEqual(saved.feed_id, self.feed_id)
            self.assertEqual(saved.started_at, record.started_at)
            self.assertIs(await repository.get_latest_for_feed(self.feed_id), saved)

    async def test_missing_runs_and_feeds_return_none(self) -> None:
        self.assertIsNone(await self.repository.get_latest_for_feed(self.feed_id))
        self.assertIsNone(await self.repository.get_latest_for_feed(self.feed_id + 1))
        record = self.run_record()
        await self.repository.add(record)
        self.assertIsNone(await self.repository.get_by_id(record.id + 1))

    async def test_latest_uses_start_time_instead_of_insertion_order_and_is_scoped_to_feed(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newest = self.run_record(
            started_at=start + timedelta(days=2),
            finished_at=start + timedelta(days=2, seconds=1),
            status="failed", error_summary="Network failure",
        )
        older = self.run_record(started_at=start)
        await self.repository.add(newest)
        await self.repository.add(older)
        other_feed = SourceFeed(
            county_id=self.county_id, ckan_resource_id=uuid4(),
            label="Disabled county feed", feed_url=f"https://example.com/{uuid4()}.xml",
            scope="county", enabled=False,
        )
        self.session.add(other_feed)
        await self.session.flush()
        other = self.run_record(feed_id=other_feed.id, started_at=start + timedelta(days=3))
        await self.repository.add(other)
        await self.session.commit()
        self.assertGreater(older.id, newest.id)

        async with self.sessions.session() as reader:
            repository = SqlAlchemySyncRunRepository(reader)
            latest = await repository.get_latest_for_feed(self.feed_id)
            self.assertEqual(latest.id, newest.id)
            self.assertEqual(latest.status, "failed")
            self.assertEqual((await repository.get_latest_for_feed(other_feed.id)).id, other.id)
            self.assertIsNotNone(await repository.get_by_id(other.id))

    async def test_latest_breaks_equal_start_time_ties_by_descending_id_and_includes_running(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = self.run_record(
            started_at=start, finished_at=start, status="succeeded", http_status=200
        )
        second = self.run_record(started_at=start)
        await self.repository.add(first)
        await self.repository.add(second)
        await self.session.commit()
        async with self.sessions.session() as reader:
            latest = await SqlAlchemySyncRunRepository(reader).get_latest_for_feed(self.feed_id)
            self.assertEqual(latest.id, second.id)
            self.assertEqual(latest.status, "running")

    async def test_loaded_outcome_and_counts_are_saved_on_caller_commit(self) -> None:
        record = self.run_record()
        await self.repository.add(record)
        await self.session.commit()
        async with self.sessions.session() as writer:
            loaded = await SqlAlchemySyncRunRepository(writer).get_by_id(record.id)
            loaded.status = "succeeded"
            loaded.finished_at = loaded.started_at + timedelta(seconds=5)
            loaded.http_status = 200
            loaded.items_seen, loaded.items_added = 6, 2
            loaded.items_updated, loaded.items_invalid = 3, 1
            await writer.commit()
        async with self.sessions.session() as reader:
            saved = await SqlAlchemySyncRunRepository(reader).get_by_id(record.id)
            self.assertEqual(saved.status, "succeeded")
            self.assertEqual(saved.finished_at, saved.started_at + timedelta(seconds=5))
            self.assertEqual(saved.http_status, 200)
            self.assertEqual((saved.items_seen, saved.items_added, saved.items_updated, saved.items_invalid), (6, 2, 3, 1))

    async def test_explicit_rollback_discards_record_and_keeps_session_usable(self) -> None:
        record = self.run_record()
        await self.repository.add(record)
        record_id = record.id
        await self.session.rollback()
        self.assertIsNone(await self.repository.get_by_id(record_id))
        replacement = self.run_record()
        await self.repository.add(replacement)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySyncRunRepository(reader)
            self.assertIsNone(await repository.get_by_id(record_id))
            self.assertIsNotNone(await repository.get_by_id(replacement.id))

    async def test_constraint_error_propagates_and_caller_can_rollback_all_writes(self) -> None:
        async with self.sessions.session() as writer:
            repository = SqlAlchemySyncRunRepository(writer)
            pending = self.run_record()
            await repository.add(pending)
            pending_id = pending.id
            with self.assertRaises(IntegrityError):
                await repository.add(self.run_record(items_seen=-1))
            await writer.rollback()
            self.assertIsNone(await repository.get_by_id(pending_id))
        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemySyncRunRepository(reader).get_by_id(pending_id))

    async def test_closing_context_without_commit_discards_record(self) -> None:
        async with self.sessions.session() as writer:
            record = self.run_record()
            await SqlAlchemySyncRunRepository(writer).add(record)
            record_id = record.id
        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemySyncRunRepository(reader).get_by_id(record_id))

    async def test_eu_history_is_excluded_and_unsupported_parents_are_rejected(self) -> None:
        legacy_feed = SourceFeed(
            ckan_resource_id=uuid4(), label="Legacy EU feed",
            feed_url=f"https://example.com/{uuid4()}.xml", scope="eu",
        )
        legacy_record = SyncRun(feed=legacy_feed)
        self.session.add(legacy_record)
        await self.session.commit()
        self.assertIsNone(await self.repository.get_by_id(legacy_record.id))
        self.assertIsNone(await self.repository.get_latest_for_feed(legacy_feed.id))
        async with self.sessions.session() as reader:
            repository = SqlAlchemySyncRunRepository(reader)
            self.assertIsNone(await repository.get_by_id(legacy_record.id))
            self.assertIsNone(await repository.get_latest_for_feed(legacy_feed.id))
        for feed_id in [legacy_feed.id, legacy_feed.id + 1, None]:
            with self.subTest(feed_id=feed_id), self.assertRaisesRegex(ValueError, "county"):
                await self.repository.add(self.run_record(feed_id=feed_id))
        await self.repository.add(self.run_record())
        await self.session.commit()
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count(SyncRun.id))), 2)
