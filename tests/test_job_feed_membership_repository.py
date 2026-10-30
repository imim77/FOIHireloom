from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.dao.concrete.sqla_job_feed_membership import (
    SqlAlchemyJobFeedMembershipRepository,
)
from FOIHireloom.dao.interfaces.job_feed_membership import JobFeedMembershipRepository


class JobFeedMembershipRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        job = self.new_job()
        feed = SourceFeed(
            county=County(code="zagreb", name="Grad Zagreb"),
            ckan_resource_id=uuid4(), label="Poslovi u Gradu Zagrebu",
            feed_url=f"https://example.com/{uuid4()}.xml", scope="county",
        )
        self.session.add_all([job, feed])
        await self.session.commit()
        self.job_id, self.feed_id, self.county_id = job.id, feed.id, feed.county_id
        self.repository: JobFeedMembershipRepository = SqlAlchemyJobFeedMembershipRepository(self.session)
        self.sessions = SessionManager(self.engine)

    def new_job(self) -> Job:
        return Job(provider="hzz", canonical_url=f"https://example.com/jobs/{uuid4()}", content_hash="hash")

    def new_feed(self, **overrides: object) -> SourceFeed:
        values = {
            "county_id": self.county_id, "ckan_resource_id": uuid4(),
            "label": "County feed", "feed_url": f"https://example.com/{uuid4()}.xml",
            "scope": "county",
        }
        return SourceFeed(**(values | overrides))

    def membership(self, **overrides: object) -> JobFeedMembership:
        values = {
            "job_id": self.job_id, "feed_id": self.feed_id,
        }
        return JobFeedMembership(**(values | overrides))

    async def test_add_flushes_observation_defaults_without_committing(self) -> None:
        membership = self.membership()
        self.assertIsNone(await self.repository.add(membership))
        self.assertEqual(membership.presence_status, "present")
        self.assertIsNone(membership.missing_since_at)
        self.assertIsNotNone(membership.first_seen_at.tzinfo)
        self.assertEqual(membership.first_seen_at, membership.last_seen_at)
        self.assertIs(await self.repository.get_by_job_and_feed(self.job_id, self.feed_id), membership)
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(JobFeedMembership, (self.job_id, self.feed_id)))

    async def test_explicit_commit_makes_membership_visible_to_another_session(self) -> None:
        membership = self.membership()
        await self.repository.add(membership)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobFeedMembershipRepository(reader)
            saved = await repository.get_by_job_and_feed(self.job_id, self.feed_id)
            self.assertIsNotNone(saved)
            self.assertIsNot(saved, membership)
            self.assertEqual(saved.presence_status, "present")
            self.assertEqual(saved.first_seen_at, membership.first_seen_at)
            self.assertEqual(await repository.list_for_feed(self.feed_id), [saved])

    async def test_missing_memberships_and_feeds_return_none_or_empty_list(self) -> None:
        self.assertIsNone(await self.repository.get_by_job_and_feed(self.job_id, self.feed_id))
        self.assertEqual(await self.repository.list_for_feed(self.feed_id), [])
        self.assertEqual(await self.repository.list_for_feed(self.feed_id + 1), [])
        await self.repository.add(self.membership())
        self.assertIsNone(await self.repository.get_by_job_and_feed(self.job_id + 1, self.feed_id))
        self.assertIsNone(await self.repository.get_by_job_and_feed(self.job_id, self.feed_id + 1))

    async def test_pair_lookup_and_ordered_list_keep_jobs_and_feeds_separate(self) -> None:
        second_job, second_feed = self.new_job(), self.new_feed(enabled=False)
        self.session.add_all([second_job, second_feed])
        await self.session.flush()
        later_job = self.membership(job_id=second_job.id)
        await self.repository.add(later_job)
        first_job = self.membership()
        await self.repository.add(first_job)
        other_feed = self.membership(feed_id=second_feed.id)
        await self.repository.add(other_feed)
        later_job.presence_status = "missing"
        later_job.missing_since_at = later_job.last_seen_at + timedelta(seconds=1)
        await self.session.commit()

        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobFeedMembershipRepository(reader)
            memberships = await repository.list_for_feed(self.feed_id)
            self.assertEqual([row.job_id for row in memberships], [self.job_id, second_job.id])
            self.assertEqual([row.presence_status for row in memberships], ["present", "missing"])
            self.assertIs(await repository.get_by_job_and_feed(self.job_id, self.feed_id), memberships[0])
            other = await repository.get_by_job_and_feed(self.job_id, second_feed.id)
            self.assertEqual((other.job_id, other.feed_id), (self.job_id, second_feed.id))
            self.assertEqual(await repository.list_for_feed(second_feed.id), [other])
            self.assertEqual(await reader.scalar(select(func.count(Job.id))), 2)

    async def test_loaded_presence_changes_persist_on_caller_commit(self) -> None:
        await self.repository.add(self.membership())
        await self.session.commit()
        async with self.sessions.session() as writer:
            loaded = await SqlAlchemyJobFeedMembershipRepository(writer).get_by_job_and_feed(
                self.job_id, self.feed_id
            )
            loaded.presence_status = "missing"
            loaded.missing_since_at = loaded.last_seen_at
            await writer.commit()
        async with self.sessions.session() as reader:
            saved = await SqlAlchemyJobFeedMembershipRepository(reader).get_by_job_and_feed(
                self.job_id, self.feed_id
            )
            self.assertEqual(saved.presence_status, "missing")

    async def test_missing_and_reappearance_preserve_job_status_and_other_feed(self) -> None:
        second_feed = self.new_feed()
        self.session.add(second_feed)
        await self.session.flush()
        membership = self.membership()
        await self.repository.add(membership)
        await self.repository.add(self.membership(feed_id=second_feed.id))
        await self.session.commit()
        first_seen, last_seen = membership.first_seen_at, membership.last_seen_at
        async with self.sessions.session() as writer:
            loaded = await SqlAlchemyJobFeedMembershipRepository(writer).get_by_job_and_feed(
                self.job_id, self.feed_id
            )
            loaded.presence_status = "missing"
            loaded.missing_since_at = last_seen + timedelta(seconds=1)
            await writer.commit()
        async with self.sessions.session() as writer:
            repository = SqlAlchemyJobFeedMembershipRepository(writer)
            missing = await repository.get_by_job_and_feed(self.job_id, self.feed_id)
            self.assertEqual(missing.presence_status, "missing")
            self.assertEqual(missing.first_seen_at, first_seen)
            self.assertEqual(missing.last_seen_at, last_seen)
            self.assertEqual((await repository.get_by_job_and_feed(self.job_id, second_feed.id)).presence_status, "present")
            self.assertEqual((await writer.get(Job, self.job_id)).availability_status, "unknown")
            missing.presence_status, missing.missing_since_at = "present", None
            missing.last_seen_at = last_seen + timedelta(seconds=2)
            await writer.commit()
        async with self.sessions.session() as reader:
            saved = await SqlAlchemyJobFeedMembershipRepository(reader).get_by_job_and_feed(
                self.job_id, self.feed_id
            )
            self.assertEqual(saved.presence_status, "present")
            self.assertIsNone(saved.missing_since_at)
            self.assertEqual(saved.first_seen_at, first_seen)
            self.assertEqual(saved.last_seen_at, last_seen + timedelta(seconds=2))
            self.assertEqual((await reader.get(Job, self.job_id)).availability_status, "unknown")

    async def test_explicit_rollback_discards_membership_and_keeps_session_usable(self) -> None:
        await self.repository.add(self.membership())
        await self.session.rollback()
        self.assertIsNone(await self.repository.get_by_job_and_feed(self.job_id, self.feed_id))
        await self.repository.add(self.membership())
        await self.session.commit()
        async with self.sessions.session() as reader:
            self.assertIsNotNone(await reader.get(JobFeedMembership, (self.job_id, self.feed_id)))

    async def test_duplicate_pair_error_propagates_and_rolls_back_other_pending_membership(self) -> None:
        await self.repository.add(self.membership())
        second_job = self.new_job()
        self.session.add(second_job)
        await self.session.commit()
        async with self.sessions.session() as writer:
            repository = SqlAlchemyJobFeedMembershipRepository(writer)
            await repository.add(self.membership(job_id=second_job.id))
            with self.assertRaises(IntegrityError):
                await repository.add(self.membership())
            await writer.rollback()
            self.assertIsNone(await repository.get_by_job_and_feed(second_job.id, self.feed_id))
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(JobFeedMembership, (second_job.id, self.feed_id)))
            self.assertIsNotNone(await reader.get(JobFeedMembership, (self.job_id, self.feed_id)))

    async def test_invalid_job_error_propagates_and_caller_can_rollback(self) -> None:
        async with self.sessions.session() as writer:
            repository = SqlAlchemyJobFeedMembershipRepository(writer)
            await repository.add(self.membership())
            with self.assertRaises(IntegrityError):
                await repository.add(self.membership(job_id=self.job_id + 1))
            await writer.rollback()
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(JobFeedMembership, (self.job_id, self.feed_id)))

    async def test_closing_context_without_commit_discards_membership(self) -> None:
        async with self.sessions.session() as writer:
            await SqlAlchemyJobFeedMembershipRepository(writer).add(self.membership())
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(JobFeedMembership, (self.job_id, self.feed_id)))

    async def test_eu_memberships_are_excluded_and_unsupported_feeds_are_rejected(self) -> None:
        legacy_feed = self.new_feed(scope="eu", county_id=None)
        legacy = self.membership(feed=legacy_feed, feed_id=None)
        self.session.add(legacy)
        await self.session.commit()
        self.assertIsNone(await self.repository.get_by_job_and_feed(self.job_id, legacy_feed.id))
        self.assertEqual(await self.repository.list_for_feed(legacy_feed.id), [])
        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobFeedMembershipRepository(reader)
            self.assertIsNone(await repository.get_by_job_and_feed(self.job_id, legacy_feed.id))
            self.assertEqual(await repository.list_for_feed(legacy_feed.id), [])
        for feed_id in [legacy_feed.id, legacy_feed.id + 1, None]:
            with self.subTest(feed_id=feed_id), self.assertRaisesRegex(ValueError, "county"):
                await self.repository.add(self.membership(feed_id=feed_id))
        await self.repository.add(self.membership())
        await self.session.commit()
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count()).select_from(JobFeedMembership)), 2)
