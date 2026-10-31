from datetime import date
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Employer, Job, JobFeedMembership, SourceFeed
from FOIHireloom.dto.job_sync import FilledCategoryDTO
from FOIHireloom.db.session import SessionManager
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.dao.interfaces.job import JobRepository


class JobRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.repository: JobRepository = SqlAlchemyJobRepository(self.session)
        self.sessions = SessionManager(self.engine)

    def job(self, **overrides: object) -> Job:
        values = {
            "provider": "hzz",
            "canonical_url": f"https://example.com/jobs/{uuid4()}",
            "content_hash": "source-content-hash",
        }
        return Job(**(values | overrides))

    async def test_add_assigns_generated_fields_without_committing(self) -> None:
        job = self.job()
        self.assertIsNone(await self.repository.add(job))
        self.assertIsInstance(job.id, int)
        self.assertIsNotNone(job.first_seen_at.tzinfo)
        self.assertEqual(job.availability_status, "unknown")
        self.assertEqual(job.quality_flags, [])
        self.assertIs(await self.repository.get_by_id(job.id), job)

        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemyJobRepository(reader).get_by_id(job.id))

    async def test_explicit_commit_persists_job_for_another_session(self) -> None:
        job = self.job(
            title="Inženjer računarstva",
            source_job_id="00123",
            published_on=date(2026, 10, 1),
            quality_flags=["missing_deadline"],
        )
        await self.repository.add(job)
        await self.session.commit()

        async with self.sessions.session() as reader:
            saved = await SqlAlchemyJobRepository(reader).get_by_id(job.id)
            self.assertIsNotNone(saved)
            self.assertIsNot(saved, job)
            self.assertEqual(saved.title, job.title)
            self.assertEqual(saved.source_job_id, "00123")
            self.assertEqual(saved.published_on, date(2026, 10, 1))
            self.assertEqual(saved.quality_flags, ["missing_deadline"])
            self.assertIsNone(saved.employer_id)
            self.assertIsNone(saved.deadline_on)

    async def test_missing_jobs_return_none(self) -> None:
        existing = self.job(source_job_id="123")
        await self.repository.add(existing)
        self.assertIsNone(await self.repository.get_by_id(existing.id + 1))
        self.assertIsNone(await self.repository.get_by_source_job_id("hzz", "missing"))
        self.assertIsNone(await self.repository.get_by_canonical_url("hzz", "https://example.com/missing"))

    async def test_source_job_lookup_is_scoped_to_provider_and_preserves_leading_zeros(self) -> None:
        jobs = [
            self.job(source_job_id="123"),
            self.job(provider="other-provider", source_job_id="123"),
            self.job(source_job_id="00123"),
            self.job(),
            self.job(),
        ]
        for job in jobs:
            await self.repository.add(job)
        await self.session.commit()

        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobRepository(reader)
            for job in jobs[:3]:
                found = await repository.get_by_source_job_id(job.provider, job.source_job_id)
                self.assertIsNotNone(found)
                self.assertEqual(found.id, job.id)
            self.assertIsNone(await repository.get_by_source_job_id("unknown-provider", "123"))

    async def test_canonical_url_lookup_is_scoped_to_provider(self) -> None:
        url = "https://example.com/jobs/shared"
        jobs = [
            self.job(canonical_url=url),
            self.job(provider="other-provider", canonical_url=url),
            self.job(),
        ]
        for job in jobs:
            await self.repository.add(job)
        await self.session.commit()

        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobRepository(reader)
            for job in jobs:
                found = await repository.get_by_canonical_url(job.provider, job.canonical_url)
                self.assertIsNotNone(found)
                self.assertEqual(found.id, job.id)
            self.assertIsNone(await repository.get_by_canonical_url("unknown-provider", url))

    async def test_explicit_rollback_discards_job_and_session_remains_usable(self) -> None:
        job = self.job()
        await self.repository.add(job)
        job_id = job.id
        await self.session.rollback()

        self.assertIsNone(await self.repository.get_by_id(job_id))
        replacement = self.job()
        await self.repository.add(replacement)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobRepository(reader)
            self.assertIsNone(await repository.get_by_id(job_id))
            self.assertIsNotNone(await repository.get_by_id(replacement.id))

    async def test_closing_context_without_commit_discards_job(self) -> None:
        async with self.sessions.session() as writer:
            job = self.job()
            repository = SqlAlchemyJobRepository(writer)
            await repository.add(job)
            job_id = job.id
            self.assertIs(await repository.get_by_id(job_id), job)

        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemyJobRepository(reader).get_by_id(job_id))

    async def test_unique_errors_propagate_and_caller_can_roll_back_all_pending_writes(self) -> None:
        existing = self.job(source_job_id="123")
        await self.repository.add(existing)
        await self.session.commit()

        for duplicate in [
            {"source_job_id": existing.source_job_id},
            {"canonical_url": existing.canonical_url},
        ]:
            with self.subTest(duplicate=duplicate):
                async with self.sessions.session() as writer:
                    repository = SqlAlchemyJobRepository(writer)
                    pending = self.job()
                    await repository.add(pending)
                    pending_id = pending.id
                    with self.assertRaises(IntegrityError):
                        await repository.add(self.job(**duplicate))
                    await writer.rollback()
                    self.assertIsNone(await repository.get_by_id(pending_id))
                    self.assertIsNotNone(await repository.get_by_id(existing.id))

                async with self.sessions.session() as reader:
                    self.assertIsNone(await SqlAlchemyJobRepository(reader).get_by_id(pending_id))

    async def test_repositories_and_other_writes_share_the_callers_transaction(self) -> None:
        employer = Employer(name="Poslodavac")
        self.session.add(employer)
        first = self.job(employer=employer)
        other_repository = SqlAlchemyJobRepository(self.session)
        await self.repository.add(first)
        second = self.job(employer=employer)
        await other_repository.add(second)
        self.assertIs(await other_repository.get_by_id(first.id), first)
        self.assertIs(await self.repository.get_by_id(second.id), second)
        first_id, second_id, employer_id = first.id, second.id, employer.id
        await self.session.rollback()

        async with self.sessions.session() as reader:
            repository = SqlAlchemyJobRepository(reader)
            self.assertIsNone(await repository.get_by_id(first_id))
            self.assertIsNone(await repository.get_by_id(second_id))
            self.assertIsNone(await reader.get(Employer, employer_id))

    async def test_loaded_job_updates_belong_to_the_callers_session(self) -> None:
        job = self.job()
        await self.repository.add(job)
        await self.session.commit()

        async with self.sessions.session() as writer:
            loaded = await SqlAlchemyJobRepository(writer).get_by_canonical_url(
                job.provider, job.canonical_url
            )
            self.assertIsNotNone(loaded)
            loaded.title = "Ažurirani naslov"
            loaded.quality_flags.append("missing_deadline")
            await writer.commit()

        async with self.sessions.session() as reader:
            saved = await SqlAlchemyJobRepository(reader).get_by_id(job.id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.title, "Ažurirani naslov")
            self.assertEqual(saved.quality_flags, ["missing_deadline"])

    async def test_category_evidence_and_fills_skip_description_categories(self) -> None:
        feeds = [
            SourceFeed(ckan_resource_id=uuid4(), label="Zanimanje", scope="occupation",
                       feed_url=f"https://example.com/{uuid4()}.xml", **mapping)
            for mapping in (
                {"mapped_category": "STRUČNJACI U PROMETU", "mapping_status": "confirmed", "mapping_matching_examples": 3,
                 "mapping_contradicting_examples": 0, "mapping_verified_at": func.now()},
                {"mapped_category": "TEKSTILCI I KOŽARI", "mapping_status": "too_few_examples",
                 "mapping_matching_examples": 1, "mapping_contradicting_examples": 0, "mapping_verified_at": func.now()},
            )
        ]
        explicit = self.job(category="DIREKTORI, RAVNATELJI, ČELNICI", category_source="description")
        unknown, outside = self.job(), self.job()
        self.session.add_all([*feeds, explicit, unknown, outside])
        await self.session.flush()
        self.session.add_all([
            JobFeedMembership(job_id=job.id, feed_id=feed.id, presence_status=status,
                              missing_since_at=func.now() if status == "missing" else None)
            for job, feed, status in ((explicit, feeds[1], "present"), (unknown, feeds[1], "missing"),
                                      (unknown, feeds[0], "present"), (outside, feeds[0], "present"))
        ])
        await self.session.flush()

        evidence = await self.repository.list_category_evidence(feeds[1].id)
        self.assertEqual([(item.job_id, item.category, item.mappings) for item in evidence],
                         [(unknown.id, None, ((feeds[0].id, "STRUČNJACI U PROMETU"),))])
        filled = FilledCategoryDTO(category="STRUČNJACI U PROMETU", feed_id=feeds[0].id)
        await self.repository.set_feed_categories({unknown.id: filled, explicit.id: filled})
        await self.session.refresh(unknown)
        await self.session.refresh(explicit)
        self.assertEqual((unknown.category, unknown.category_source, unknown.category_feed_id),
                         ("STRUČNJACI U PROMETU", "feed", feeds[0].id))
        self.assertEqual((explicit.category, explicit.category_source), ("DIREKTORI, RAVNATELJI, ČELNICI", "description"))
        self.assertEqual((await self.repository.list_category_evidence(feeds[0].id))[0].category, "STRUČNJACI U PROMETU")
        await self.repository.set_feed_categories({unknown.id: None})
        await self.session.refresh(unknown)
        self.assertEqual((unknown.category, unknown.category_source, unknown.category_feed_id), (None, None, None))
