import asyncio
from contextlib import suppress
from datetime import timedelta
from uuid import uuid4

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Employer, Job, JobFeedMembership, SourceFeed, SyncRun
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWork, SqlAlchemyUnitOfWorkFactory, UnitOfWork
from FOIHireloom.exceptions import ConflictError
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.dao.concrete.sqla_source_feed import SqlAlchemySourceFeedRepository
from FOIHireloom.dao.concrete.sqla_sync_run import SqlAlchemySyncRunRepository


class UnitOfWorkTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.sessions = SessionManager(self.engine)

    def job(self, **overrides: object) -> Job:
        values = {
            "provider": "hzz",
            "canonical_url": f"https://example.com/jobs/{uuid4()}",
            "content_hash": "source-content-hash",
        }
        return Job(**(values | overrides))

    def feed(self) -> SourceFeed:
        return SourceFeed(
            county=County(code="zagreb", name="Grad Zagreb"),
            ckan_resource_id=uuid4(),
            label="Poslovi u Gradu Zagrebu",
            feed_url=f"https://example.com/{uuid4()}.xml",
            scope="county",
        )

    async def persisted(self, job_id: int) -> Job | None:
        async with self.sessions.session() as reader:
            return await SqlAlchemyJobRepository(reader).get_by_id(job_id)

    async def test_explicit_commit_persists_related_records_together(self) -> None:
        work: UnitOfWork = SqlAlchemyUnitOfWork(self.sessions)
        async with work as active:
            self.assertIs(active, work)
            first = self.job(employer=Employer(name="Poslodavac"))
            await active.jobs.add(first)
            second = self.job(employer_id=first.employer_id)
            await active.jobs.add(second)
            self.assertIs(await active.jobs.get_by_id(first.id), first)
            self.assertIsNone(await self.persisted(first.id))
            self.assertIsNone(await self.persisted(second.id))
            await active.commit()

        self.assertEqual((await self.persisted(first.id)).employer_id, first.employer_id)
        self.assertEqual((await self.persisted(second.id)).employer_id, first.employer_id)
        async with self.sessions.session() as reader:
            employer = await reader.get(Employer, first.employer_id)
            self.assertEqual(employer.name, "Poslodavac")
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_normal_exit_without_commit_rolls_back(self) -> None:
        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            job = self.job()
            await work.jobs.add(job)
            job_id = job.id

        self.assertIsNone(await self.persisted(job_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_exception_propagates_and_rolls_back_all_related_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid source item"):
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                job = self.job(employer=Employer(name="Poslodavac"))
                await work.jobs.add(job)
                job_id, employer_id = job.id, job.employer_id
                raise ValueError("invalid source item")

        self.assertIsNone(await self.persisted(job_id))
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(Employer, employer_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_transaction_time_is_stable_within_and_advances_across_transactions(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            first = await work.transaction_time()
            await asyncio.sleep(0.01)
            self.assertEqual(await work.transaction_time(), first)
            self.assertIsNotNone(first.tzinfo)
        async with work:
            self.assertGreater(await work.transaction_time(), first)

    async def test_failed_flush_rolls_back_earlier_writes_and_allows_reuse(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        with self.assertRaises(ConflictError):
            async with work:
                first = self.job(source_job_id="123")
                await work.jobs.add(first)
                first_id = first.id
                await work.jobs.add(self.job(source_job_id="123"))

        self.assertIsNone(await self.persisted(first_id))
        async with work:
            replacement = self.job(source_job_id="123")
            await work.jobs.add(replacement)
            await work.commit()
        self.assertIsNotNone(await self.persisted(replacement.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_failed_commit_rolls_back_insert_and_update(self) -> None:
        first, second = self.job(), self.job()
        original_url = second.canonical_url
        self.session.add_all([first, second])
        await self.session.commit()

        with self.assertRaises(ConflictError):
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                pending = self.job()
                await work.jobs.add(pending)
                pending_id = pending.id
                loaded = await work.jobs.get_by_id(second.id)
                loaded.canonical_url = first.canonical_url
                await work.commit()

        self.assertIsNone(await self.persisted(pending_id))
        self.assertEqual((await self.persisted(second.id)).canonical_url, original_url)
        self.assertIsNotNone(await self.persisted(first.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_explicit_rollback_keeps_context_usable(self) -> None:
        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            discarded = self.job()
            await work.jobs.add(discarded)
            discarded_id = discarded.id
            await work.rollback()
            self.assertIsNone(await work.jobs.get_by_id(discarded_id))
            replacement = self.job()
            await work.jobs.add(replacement)
            await work.commit()

        self.assertIsNone(await self.persisted(discarded_id))
        self.assertIsNotNone(await self.persisted(replacement.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_changes_after_commit_still_require_another_commit(self) -> None:
        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            committed = self.job()
            await work.jobs.add(committed)
            committed_id = committed.id
            await work.commit()
            discarded = self.job()
            await work.jobs.add(discarded)
            discarded_id = discarded.id

        self.assertIsNotNone(await self.persisted(committed_id))
        self.assertIsNone(await self.persisted(discarded_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_exception_after_commit_preserves_already_committed_data(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "after commit"):
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                committed = self.job()
                await work.jobs.add(committed)
                committed_id = committed.id
                await work.commit()
                raise RuntimeError("after commit")

        self.assertIsNotNone(await self.persisted(committed_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_loaded_updates_require_commit(self) -> None:
        job = self.job(title="Original")
        self.session.add(job)
        await self.session.commit()

        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            loaded = await work.jobs.get_by_id(job.id)
            loaded.title = "Discarded"
        self.assertEqual((await self.persisted(job.id)).title, "Original")

        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            loaded = await work.jobs.get_by_id(job.id)
            loaded.title = "Committed"
            await work.commit()
        self.assertEqual((await self.persisted(job.id)).title, "Committed")
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_operations_outside_active_context_are_rejected(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, "active"):
                _ = work.jobs
            with self.assertRaisesRegex(RuntimeError, "active"):
                _ = work.counties
            with self.assertRaisesRegex(RuntimeError, "active"):
                _ = work.job_feed_memberships
            with self.assertRaisesRegex(RuntimeError, "active"):
                _ = work.source_feeds
            with self.assertRaisesRegex(RuntimeError, "active"):
                _ = work.sync_runs
            with self.assertRaisesRegex(RuntimeError, "active"):
                await work.commit()
            with self.assertRaisesRegex(RuntimeError, "active"):
                await work.rollback()
            async with work:
                pass
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_nested_entry_is_rejected_without_disrupting_outer_transaction(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            job = self.job()
            await work.jobs.add(job)
            with self.assertRaisesRegex(RuntimeError, "already active"):
                async with work:
                    self.fail("Nested entry must not succeed")
            self.assertIs(await work.jobs.get_by_id(job.id), job)
            await work.commit()

        self.assertIsNotNone(await self.persisted(job.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_sequential_reuse_creates_a_fresh_repository_and_transaction(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            previous_repository = work.jobs
            previous_counties = work.counties
            previous_memberships = work.job_feed_memberships
            previous_source_feeds = work.source_feeds
            previous_sync_runs = work.sync_runs
            discarded = self.job()
            await work.jobs.add(discarded)
            discarded_id = discarded.id

        async with work:
            self.assertIsNot(work.jobs, previous_repository)
            self.assertIsNot(work.counties, previous_counties)
            self.assertIsNot(work.job_feed_memberships, previous_memberships)
            self.assertIsNot(work.source_feeds, previous_source_feeds)
            self.assertIsNot(work.sync_runs, previous_sync_runs)
            self.assertIsNone(await work.jobs.get_by_id(discarded_id))
            committed = self.job()
            await work.jobs.add(committed)
            await work.commit()

        self.assertIsNone(await self.persisted(discarded_id))
        self.assertIsNotNone(await self.persisted(committed.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_source_feed_and_job_membership_commit_in_the_same_transaction(self) -> None:
        work: UnitOfWork = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            feed = self.feed()
            await work.source_feeds.add(feed)
            job = self.job()
            await work.jobs.add(job)
            membership = JobFeedMembership(
                job_id=job.id, feed_id=feed.id, source_item={"title": "Programer"}
            )
            await work.job_feed_memberships.add(membership)
            self.assertIs(
                await work.job_feed_memberships.get_by_job_and_feed(job.id, feed.id), membership
            )
            self.assertEqual(await work.job_feed_memberships.list_for_feed(feed.id), [membership])
            self.assertIs(await work.source_feeds.get_by_id(feed.id), feed)
            async with self.sessions.session() as reader:
                self.assertIsNone(await reader.get(SourceFeed, feed.id))
                self.assertIsNone(await reader.get(JobFeedMembership, (job.id, feed.id)))
            await work.commit()

        async with self.sessions.session() as reader:
            feeds = SqlAlchemySourceFeedRepository(reader)
            self.assertIsNotNone(await feeds.get_by_ckan_resource_id(feed.ckan_resource_id))
            self.assertEqual([saved.id for saved in await feeds.list_enabled()], [feed.id])
            self.assertIsNotNone(await SqlAlchemyJobRepository(reader).get_by_id(job.id))
            membership = await reader.get(JobFeedMembership, (job.id, feed.id))
            self.assertEqual(membership.source_item, {"title": "Programer"})
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_uncommitted_source_feed_job_and_membership_are_rolled_back_together(self) -> None:
        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            feed = self.feed()
            await work.source_feeds.add(feed)
            job = self.job()
            await work.jobs.add(job)
            await work.job_feed_memberships.add(JobFeedMembership(
                job_id=job.id, feed_id=feed.id, source_item={"title": "Programer"}
            ))
            feed_id, job_id, county_id = feed.id, job.id, feed.county_id

        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(SourceFeed, feed_id))
            self.assertIsNone(await reader.get(Job, job_id))
            self.assertIsNone(await reader.get(JobFeedMembership, (job_id, feed_id)))
            self.assertIsNone(await reader.get(County, county_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_source_feed_error_rolls_back_both_repositories(self) -> None:
        with self.assertRaises(ConflictError) as error:
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                feed = self.feed()
                await work.source_feeds.add(feed)
                job = self.job()
                await work.jobs.add(job)
                feed_id, job_id = feed.id, job.id
                await work.source_feeds.add(SourceFeed(
                    county_id=feed.county_id,
                    ckan_resource_id=feed.ckan_resource_id,
                    label="Duplicate source",
                    feed_url=f"https://example.com/{uuid4()}.xml",
                    scope="county",
                ))

        self.assertIn("uq_source_feeds_ckan_resource_id", str(error.exception))
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(SourceFeed, feed_id))
            self.assertIsNone(await reader.get(Job, job_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_source_feed_job_and_sync_outcome_commit_together(self) -> None:
        work: UnitOfWork = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            feed = self.feed()
            await work.source_feeds.add(feed)
            record = SyncRun(feed_id=feed.id)
            await work.sync_runs.add(record)
            job = self.job()
            await work.jobs.add(job)
            self.assertIs(await work.sync_runs.get_latest_for_feed(feed.id), record)
            record.status, record.http_status = "succeeded", 200
            record.finished_at = record.started_at + timedelta(seconds=1)
            record.items_seen, record.items_added = 1, 1
            record.items_updated, record.items_invalid = 0, 0
            feed.last_checked_at = feed.last_success_at = record.finished_at
            async with self.sessions.session() as reader:
                self.assertIsNone(await reader.get(SyncRun, record.id))
                self.assertIsNone(await reader.get(Job, job.id))
            await work.commit()

        async with self.sessions.session() as reader:
            saved = await SqlAlchemySyncRunRepository(reader).get_by_id(record.id)
            self.assertEqual(saved.status, "succeeded")
            self.assertEqual(saved.items_added, 1)
            saved_feed = await reader.get(SourceFeed, feed.id)
            self.assertEqual(saved_feed.last_success_at, saved.finished_at)
            self.assertIsNotNone(await reader.get(Job, job.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_uncommitted_source_feed_job_and_sync_run_are_rolled_back_together(self) -> None:
        async with SqlAlchemyUnitOfWork(self.sessions) as work:
            feed = self.feed()
            await work.source_feeds.add(feed)
            record = SyncRun(feed_id=feed.id)
            await work.sync_runs.add(record)
            job = self.job()
            await work.jobs.add(job)
            feed_id, run_id, job_id, county_id = feed.id, record.id, job.id, feed.county_id

        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(SourceFeed, feed_id))
            self.assertIsNone(await reader.get(SyncRun, run_id))
            self.assertIsNone(await reader.get(Job, job_id))
            self.assertIsNone(await reader.get(County, county_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_failed_run_can_be_saved_after_import_writes_are_rolled_back(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        async with work:
            feed = self.feed()
            await work.source_feeds.add(feed)
            record = SyncRun(feed_id=feed.id)
            await work.sync_runs.add(record)
            feed_id, run_id = feed.id, record.id
            await work.commit()

        with self.assertRaisesRegex(ValueError, "invalid source item") as error:
            async with work:
                job = self.job()
                await work.jobs.add(job)
                job_id = job.id
                raise ValueError("invalid source item")

        async with work:
            failed = await work.sync_runs.get_by_id(run_id)
            self.assertEqual(failed.status, "running")
            failed.status, failed.http_status = "failed", 200
            failed.finished_at = failed.started_at + timedelta(seconds=1)
            failed.error_summary = str(error.exception)
            loaded_feed = await work.source_feeds.get_by_id(feed_id)
            loaded_feed.last_checked_at = failed.finished_at
            await work.commit()

        async with self.sessions.session() as reader:
            failed = await SqlAlchemySyncRunRepository(reader).get_latest_for_feed(feed_id)
            self.assertEqual(failed.id, run_id)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.error_summary, "invalid source item")
            self.assertIsNone(await reader.get(Job, job_id))
            self.assertIsNone((await reader.get(SourceFeed, feed_id)).last_success_at)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_membership_error_rolls_back_all_repositories(self) -> None:
        with self.assertRaises(ConflictError) as error:
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                feed = self.feed()
                await work.source_feeds.add(feed)
                job = self.job()
                await work.jobs.add(job)
                record = SyncRun(feed_id=feed.id)
                await work.sync_runs.add(record)
                await work.job_feed_memberships.add(JobFeedMembership(
                    job_id=job.id, feed_id=feed.id, source_item={}
                ))
                feed_id, job_id, run_id, county_id = feed.id, job.id, record.id, feed.county_id
                await work.job_feed_memberships.add(JobFeedMembership(
                    job_id=job.id + 1, feed_id=feed.id, source_item={}
                ))

        self.assertIn("fk_job_feed_memberships_job_id_jobs", str(error.exception))
        async with self.sessions.session() as reader:
            self.assertIsNone(await reader.get(SourceFeed, feed_id))
            self.assertIsNone(await reader.get(Job, job_id))
            self.assertIsNone(await reader.get(SyncRun, run_id))
            self.assertIsNone(await reader.get(JobFeedMembership, (job_id, feed_id)))
            self.assertIsNone(await reader.get(County, county_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_concurrent_instances_have_independent_transactions(self) -> None:
        barrier = asyncio.Barrier(2)
        factory = SqlAlchemyUnitOfWorkFactory(self.sessions)

        async def write(commit: bool) -> int:
            async with factory() as work:
                job = self.job()
                await work.jobs.add(job)
                job_id = job.id
                await barrier.wait()
                if commit:
                    await work.commit()
            return job_id

        committed_id, discarded_id = await asyncio.wait_for(
            asyncio.gather(write(True), write(False)), timeout=10
        )
        self.assertIsNotNone(await self.persisted(committed_id))
        self.assertIsNone(await self.persisted(discarded_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_cancellation_rolls_back_and_releases_connection(self) -> None:
        ready = asyncio.Event()
        job = self.job()

        async def write() -> None:
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
                await work.jobs.add(job)
                ready.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(write())
        try:
            await asyncio.wait_for(ready.wait(), timeout=10)
            job_id = job.id
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.assertTrue(task.cancelled())
        self.assertIsNone(await self.persisted(job_id))
        self.assertEqual(self.engine.pool.checkedout(), 0)
