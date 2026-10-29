import asyncio
from contextlib import suppress
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Employer, Job
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWork, UnitOfWork
from FOIHireloom.persistence.impl.sqlalchemy_job_repository import SqlAlchemyJobRepository


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

    async def test_failed_flush_rolls_back_earlier_writes_and_allows_reuse(self) -> None:
        work = SqlAlchemyUnitOfWork(self.sessions)
        with self.assertRaises(IntegrityError):
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

        with self.assertRaises(IntegrityError):
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
            discarded = self.job()
            await work.jobs.add(discarded)
            discarded_id = discarded.id

        async with work:
            self.assertIsNot(work.jobs, previous_repository)
            self.assertIsNone(await work.jobs.get_by_id(discarded_id))
            committed = self.job()
            await work.jobs.add(committed)
            await work.commit()

        self.assertIsNone(await self.persisted(discarded_id))
        self.assertIsNotNone(await self.persisted(committed.id))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_concurrent_instances_have_independent_transactions(self) -> None:
        barrier = asyncio.Barrier(2)

        async def write(commit: bool) -> int:
            async with SqlAlchemyUnitOfWork(self.sessions) as work:
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
