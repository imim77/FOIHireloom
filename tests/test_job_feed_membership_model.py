from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Job, JobFeedMembership, SourceFeed


class JobFeedMembershipModelTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.job = Job(provider="hzz", canonical_url="https://example.com/job", content_hash="hash")
        self.feed = self.new_feed()
        self.session.add_all([self.job, self.feed])
        await self.session.flush()

    def new_feed(self) -> SourceFeed:
        return SourceFeed(
            ckan_resource_id=uuid4(), label="EU", scope="eu", feed_url=f"https://example.com/{uuid4()}"
        )

    def membership(self, **overrides: object) -> JobFeedMembership:
        return JobFeedMembership(**({
            "job_id": self.job.id, "feed_id": self.feed.id,
            "source_item": {"title": "Čuvar", "details": {"hours": 40}},
        } | overrides))

    async def test_same_job_can_appear_in_multiple_feeds_without_duplicate_membership(self) -> None:
        second_feed = self.new_feed()
        self.session.add(second_feed)
        await self.session.flush()
        self.session.add_all([self.membership(), self.membership(feed_id=second_feed.id)])
        await self.session.flush()
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(Job)), 1)
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(JobFeedMembership)), 2)
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.execute(insert(JobFeedMembership).values(
                    job_id=self.job.id, feed_id=self.feed.id, source_item={}
                ))

    async def test_jsonb_roundtrip_and_top_level_mutation(self) -> None:
        membership = self.membership()
        self.session.add(membership)
        await self.session.commit()
        membership.source_item["title"] = "Čuvar/ica"
        await self.session.commit()
        await self.session.refresh(membership)
        self.assertEqual(membership.source_item["title"], "Čuvar/ica")
        self.assertEqual(membership.source_item["details"], {"hours": 40})

    async def test_missing_observation_requires_time_and_does_not_close_job(self) -> None:
        now = datetime.now(timezone.utc)
        await self.assert_rejected(self.membership(presence_status="missing"))
        await self.assert_rejected(self.membership(missing_since_at=now))
        await self.assert_rejected(self.membership(presence_status="unknown"))
        await self.assert_rejected(self.membership(
            presence_status="missing", first_seen_at=now, last_seen_at=now,
            missing_since_at=now - timedelta(seconds=1),
        ))
        self.session.add(self.membership(
            presence_status="missing", first_seen_at=now, last_seen_at=now, missing_since_at=now
        ))
        await self.session.flush()
        self.assertEqual(self.job.availability_status, "unknown")

    async def test_foreign_keys_and_delete_rules(self) -> None:
        await self.assert_rejected(self.membership(job_id=999999))
        await self.assert_rejected(self.membership(feed_id=999999))
        self.session.add(self.membership())
        await self.session.flush()
        await self.session.refresh(self.feed, ["job_memberships"])
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.delete(self.feed)
                await self.session.flush()
        await self.session.delete(self.job)
        await self.session.flush()
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(JobFeedMembership)), 0)
        self.assertIsNotNone(await self.session.get(SourceFeed, self.feed.id))
