from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import SourceFeed, SyncRun


class SyncRunModelTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.feed = SourceFeed(
            ckan_resource_id=uuid4(), label="EU", feed_url="https://example.com/eu.xml", scope="eu"
        )
        self.session.add(self.feed)
        await self.session.flush()

    def run_record(self, **overrides: object) -> SyncRun:
        return SyncRun(**({"feed_id": self.feed.id} | overrides))

    async def test_new_run_has_unknown_counts_and_no_finish_time(self) -> None:
        run = self.run_record()
        self.session.add(run)
        await self.session.flush()
        self.assertEqual(run.status, "running")
        self.assertIsNone(run.finished_at)
        self.assertIsNone(run.items_seen)

    async def test_completion_requires_matching_status_and_http_code(self) -> None:
        now = datetime.now(timezone.utc)
        for status, http in [("succeeded", 200), ("not_modified", 304), ("failed", None), ("rejected", 200)]:
            run = self.run_record(
                status=status, http_status=http, started_at=now, finished_at=now
            )
            self.session.add(run)
        await self.session.flush()
        await self.assert_rejected(self.run_record(status="failed"))
        await self.assert_rejected(self.run_record(status="unknown"))
        await self.assert_rejected(self.run_record(status="running", finished_at=now))
        for status, code in [("succeeded", 304), ("not_modified", 200), ("succeeded", None), ("not_modified", None)]:
            await self.assert_rejected(
                self.run_record(status=status, http_status=code, started_at=now, finished_at=now)
            )

    async def test_rejects_negative_counts_invalid_http_and_reversed_time(self) -> None:
        for field in ["items_seen", "items_added", "items_updated", "items_invalid"]:
            await self.assert_rejected(self.run_record(**{field: -1}))
        await self.assert_rejected(self.run_record(http_status=999))
        now = datetime.now(timezone.utc)
        await self.assert_rejected(
            self.run_record(status="failed", started_at=now, finished_at=now - timedelta(seconds=1))
        )

    async def test_feed_with_run_cannot_be_deleted(self) -> None:
        self.session.add(self.run_record())
        await self.session.flush()
        await self.session.refresh(self.feed, ["sync_runs"])
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.delete(self.feed)
                await self.session.flush()
