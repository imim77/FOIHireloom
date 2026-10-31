from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Employer, Job, SourceFeed


class JobModelTests(ModelTestCase):
    def job(self, **overrides: object) -> Job:
        values = {
            "provider": "hzz",
            "canonical_url": f"https://example.com/jobs/{uuid4()}",
            "content_hash": "source-content-hash",
        }
        return Job(**(values | overrides))

    async def test_incomplete_ads_preserve_unknown_fields(self) -> None:
        job = self.job()
        other = self.job()
        self.session.add_all([job, other])
        await self.session.commit()
        self.assertIsNone(job.title)
        self.assertIsNone(job.employer_id)
        self.assertIsNone(job.deadline_on)
        self.assertEqual(job.availability_status, "unknown")
        self.assertEqual(job.quality_flags, [])
        self.assertIsNot(job.quality_flags, other.quality_flags)
        self.assertIsNotNone(job.first_seen_at.tzinfo)

    async def test_identity_is_scoped_to_provider(self) -> None:
        job = self.job(source_job_id="123")
        self.session.add(job)
        await self.session.flush()
        await self.assert_rejected(self.job(source_job_id="123"))
        await self.assert_rejected(self.job(canonical_url=job.canonical_url))
        self.session.add(self.job(provider="another-provider", source_job_id="123"))
        await self.session.flush()

    async def test_quality_flag_array_tracks_in_place_changes_and_dates_remain_dates(self) -> None:
        job = self.job(published_on=date(2026, 10, 1), deadline_on=date(2026, 10, 31))
        self.session.add(job)
        await self.session.commit()
        job.quality_flags.append("missing_title")
        await self.session.commit()
        await self.session.refresh(job)
        self.assertEqual(job.quality_flags, ["missing_title"])
        self.assertEqual(job.deadline_on, date(2026, 10, 31))

    async def test_confirmed_availability_requires_complete_evidence(self) -> None:
        now = datetime.now(timezone.utc)
        await self.assert_rejected(self.job(availability_status="confirmed_open"))
        await self.assert_rejected(
            self.job(availability_status="confirmed_closed", availability_evidence_url="https://example.com/evidence")
        )
        await self.assert_rejected(self.job(availability_checked_at=now))
        await self.assert_rejected(self.job(availability_status="invented"))
        for status in ["confirmed_open", "confirmed_closed"]:
            self.session.add(self.job(
                availability_status=status,
                availability_evidence_url="https://example.com/evidence",
                availability_checked_at=now,
            ))
        await self.session.flush()

    async def test_rejects_blank_identity_and_inconsistent_observation_times(self) -> None:
        for field in ["provider", "canonical_url", "content_hash"]:
            await self.assert_rejected(self.job(**{field: " "}))
        now = datetime.now(timezone.utc)
        await self.assert_rejected(self.job(
            first_seen_at=now, last_seen_at=now - timedelta(seconds=1), content_changed_at=now
        ))
        await self.assert_rejected(self.job(
            first_seen_at=now, last_seen_at=now, content_changed_at=now + timedelta(seconds=1)
        ))

    async def test_referenced_employer_cannot_be_deleted(self) -> None:
        employer = Employer(name="Poslodavac")
        self.session.add(self.job(employer=employer))
        await self.session.flush()
        await self.session.refresh(employer, ["jobs"])
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.delete(employer)
                await self.session.flush()

    async def test_category_records_its_source_and_filled_in_ones_their_feed(self) -> None:
        feed = SourceFeed(ckan_resource_id=uuid4(), label="Zanimanje", scope="occupation",
                          feed_url="https://example.com/kat.xml")
        self.session.add(feed)
        await self.session.flush()
        for values in (
            {},
            {"category": "STRUČNJACI U PROMETU", "category_source": "description"},
            {"category": "STRUČNJACI U PROMETU", "category_source": "feed", "category_feed_id": feed.id},
        ):
            with self.subTest(values=values):
                self.session.add(self.job(**values))
                await self.session.flush()
        for values in (
            {"category": "STRUČNJACI U PROMETU"},
            {"category_source": "description"},
            {"category": "STRUČNJACI U PROMETU", "category_source": "feed"},
            {"category": "STRUČNJACI U PROMETU", "category_source": "description", "category_feed_id": feed.id},
            {"category": "STRUČNJACI U PROMETU", "category_source": "opis"},
            {"category_feed_id": feed.id},
            {"category": "STRUČNJACI U PROMETU", "category_source": "feed", "category_feed_id": feed.id + 1},
        ):
            with self.subTest(values=values):
                await self.assert_rejected(self.job(**values))

    async def test_normalised_conditions_use_known_codes_and_need_a_fetched_page(self) -> None:
        now = datetime.now(timezone.utc)
        fetched = {"page_status": "fetched", "page_checked_at": now, "page_fetched_at": now, "page_source_hash": "h"}
        self.session.add(self.job(
            **fetched, experience_months=0, trainee=True, contract="fixed_term", employment_tags=["seasonal", "trainee"],
            full_time=False, weekly_hours=20, education_levels=["primary", "secondary_3"], accommodation="none",
            schedule_tags=["night"], transport_allowance="partial", conditions_unrecognised=["work_schedule"],
        ))
        self.session.add(self.job(**fetched, experience_months=18, trainee=False, employment_tags=[]))
        await self.session.flush()
        for values in (
            {"contract": "permanent"},
            {"conditions_unrecognised": ["experience"]},
            {"page_status": "unavailable", "page_checked_at": now, "education_levels": ["university"]},
        ):
            with self.subTest(values=values):
                await self.assert_rejected(self.job(**values))
        for values in (
            {"contract": "seasonal"},
            {"employment_tags": ["vacancy", "volunteer"]},
            {"education_levels": ["doctorate"]},
            {"accommodation": "hostel"},
            {"schedule_tags": ["evening"]},
            {"transport_allowance": "yes"},
            {"conditions_unrecognised": ["title"]},
            {"experience_months": -1, "trainee": False},
            {"experience_months": 6, "trainee": True},
            {"experience_months": 6},
            {"trainee": False},
            {"weekly_hours": 0},
        ):
            with self.subTest(values=values):
                await self.assert_rejected(self.job(**fetched, **values))
