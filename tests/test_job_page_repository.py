from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import func, select, text, update

from model_test_case import ModelTestCase

from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.dto.job_conditions import JobConditionsDTO, JobConditionsInputDTO, RawJobConditionsDTO

PAGE = ParsedJobPageDTO(
    title="KUHAR/ICA", work_place="PULA-POLA, ISTARSKA ŽUPANIJA", workers_needed=2,
    employment_type="Na određeno; sezonski poslovi", working_hours="Puno radno vrijeme", work_schedule=None,
    accommodation="Zajednički smještaj", transport_allowance="U cijelosti", valid_from=date(2026, 10, 27),
    valid_until=date(2026, 11, 27), education="Srednja škola 3 godine", experience="Nije važno",
    description_text="Rad u kuhinji.", employer_name="RESTORAN d.o.o.",
)
# PAGE's conditions; "sezonski poslovi" is not HZZ wording, so the employment type is unrecognised.
CONDITIONS = JobConditionsDTO(
    experience_months=0, trainee=False, full_time=True, education_levels=("secondary_3",), accommodation="shared",
    transport_allowance="full", unrecognised=("employment_type",),
)


class JobPageRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        county = County(code="istarska", name="Istarska županija")
        self.session.add(county)
        await self.session.flush()
        feed = SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label="IS", scope="county",
                          feed_url="http://burzarada.hzz.hr/rss/rsszup18.xml")
        self.session.add(feed)
        await self.session.flush()
        self.ids = {}
        for key, published, presence in (("old", date(2026, 10, 1), "present"), ("new", date(2026, 10, 29), "present"),
                                         ("undated", None, "present"), ("gone", date(2026, 10, 30), "missing")):
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://burzarada.hzz.hr/x?WebSifra={key}",
                      content_hash=f"hash-{key}", published_on=published)
            self.session.add(job)
            await self.session.flush()
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feed.id, presence_status=presence,
                                               missing_since_at=func.now() if presence == "missing" else None))
            self.ids[key] = job.id
        await self.session.commit()
        self.repository = SqlAlchemyJobRepository(self.session)
        self.now = await self.session.scalar(select(func.now()))

    async def candidates(self, retry_hours: float = 24) -> list[int]:
        targets = await self.repository.list_page_candidates(self.now - timedelta(hours=retry_hours), 10)
        return [target.id for target in targets]

    async def test_listed_jobs_without_a_page_are_due_newest_first(self) -> None:
        self.assertEqual(await self.candidates(), [self.ids["new"], self.ids["old"], self.ids["undated"]])
        self.assertEqual(await self.repository.count_page_candidates(self.now), 3)
        targets = await self.repository.list_page_candidates(self.now, 1)
        self.assertEqual((targets[0].id, targets[0].content_hash), (self.ids["new"], "hash-new"))

    async def test_fetched_page_is_stored_and_due_again_only_when_feed_content_changes(self) -> None:
        await self.repository.record_page(self.ids["new"], PAGE, CONDITIONS, "hash-new", self.now)
        await self.session.commit()
        job = await self.session.get(Job, self.ids["new"])
        self.assertEqual((job.page_status, job.page_checked_at, job.page_fetched_at, job.page_source_hash),
                         ("fetched", self.now, self.now, "hash-new"))
        self.assertEqual((job.page_valid_until, job.page_work_place, job.page_workers_needed, job.page_employer_name),
                         (date(2026, 11, 27), "PULA-POLA, ISTARSKA ŽUPANIJA", 2, "RESTORAN d.o.o."))
        self.assertEqual((job.page_accommodation, job.accommodation, job.page_education, job.education_levels),
                         ("Zajednički smještaj", "shared", "Srednja škola 3 godine", ["secondary_3"]))
        self.assertEqual((job.contract, job.employment_tags, job.conditions_unrecognised),
                         (None, None, ["employment_type"]))
        self.assertNotIn(self.ids["new"], await self.candidates())

        await self.session.execute(update(Job).where(Job.id == self.ids["new"]).values(content_hash="hash-changed"))
        await self.session.commit()
        self.assertIn(self.ids["new"], await self.candidates())

    async def test_problems_keep_earlier_values_and_are_retried_later(self) -> None:
        await self.repository.record_page(self.ids["old"], PAGE, CONDITIONS, "hash-old", self.now - timedelta(days=2))
        await self.repository.record_page_problem(self.ids["old"], "unavailable", "error page", self.now)
        await self.repository.record_page_problem(self.ids["undated"], "failed", "HTTP 503", self.now)
        await self.session.commit()
        job = await self.session.get(Job, self.ids["old"])
        self.assertEqual((job.page_status, job.page_error, job.page_valid_until), ("unavailable", "error page",
                                                                                  date(2026, 11, 27)))
        self.assertEqual((job.accommodation, job.conditions_unrecognised), ("shared", ["employment_type"]))
        self.assertEqual(await self.candidates(retry_hours=24), [self.ids["new"]])
        self.assertEqual(await self.candidates(retry_hours=-1), [self.ids["new"], self.ids["old"], self.ids["undated"]])
        with self.assertRaises(ValueError):
            await self.repository.record_page_problem(self.ids["old"], "fetched", "no", self.now)

    async def test_page_status_constraints(self) -> None:
        for statement in (
            "UPDATE jobs SET page_status = 'closed', page_checked_at = now()",
            "UPDATE jobs SET page_status = 'failed'",
            "UPDATE jobs SET page_checked_at = now()",
            "UPDATE jobs SET page_status = 'fetched', page_checked_at = now(), page_fetched_at = now()",
        ):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(Exception, "ck_jobs_page"):
                    async with self.session.begin_nested():
                        await self.session.execute(text(statement))

    async def test_condition_inputs_cover_fetched_jobs_and_set_conditions_replaces_normalised_values(self) -> None:
        await self.repository.record_page(self.ids["new"], PAGE, CONDITIONS, "hash-new", self.now)
        await self.repository.record_page(self.ids["gone"], PAGE, JobConditionsDTO(), "hash-gone", self.now)
        raw = RawJobConditionsDTO.model_validate(PAGE)
        self.assertEqual(await self.repository.list_condition_inputs(), [
            JobConditionsInputDTO(job_id=self.ids["new"], raw=raw, stored=CONDITIONS),
            JobConditionsInputDTO(job_id=self.ids["gone"], raw=raw, stored=JobConditionsDTO()),
        ])

        permanent = JobConditionsDTO(contract="permanent", employment_tags=("seasonal", "trainee"))
        await self.repository.set_conditions({self.ids["new"]: permanent, self.ids["gone"]: CONDITIONS})
        await self.repository.set_conditions({})
        await self.session.commit()
        inputs = await self.repository.list_condition_inputs()
        self.assertEqual([(job.raw, job.stored) for job in inputs], [(raw, permanent), (raw, CONDITIONS)])
