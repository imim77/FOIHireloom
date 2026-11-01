from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, text, update

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.job_comparison import ComparisonCellDTO, JobComparisonConditionsDTO, JobComparisonDTO
from FOIHireloom.dto.job_conditions import RawJobConditionsDTO
from FOIHireloom.dto.job_search import JobSearchFiltersDTO
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError
from FOIHireloom.services import (
    CroatianCountyCatalog,
    JobComparator,
    JobConditionMatcher,
    JobConditionsNormalizer,
    JobSearchService,
)

ASPECTS = ["experience", "education", "contract", "working_time", "accommodation", "deadline"]
# The page field each aspect's evidence is, but the deadline's.
EVIDENCE_FIELDS = {"experience": "experience", "education": "education", "contract": "employment_type",
                   "working_time": "working_hours", "accommodation": "accommodation"}
UNREAD = "the job's HZZ page has not been read yet"
# Someone with six months of experience and a 4-year secondary school who wants a permanent full-time job with
# accommodation.
WANTED = JobComparisonConditionsDTO(max_experience_months=6, contract="permanent", full_time=True,
                                    education="secondary_4", accommodation=True)


class JobComparisonTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.today = await self.session.scalar(text("SELECT (now() AT TIME ZONE 'Europe/Zagreb')::date"))
        county = County(code="varazdinska", name="Varaždinska županija")
        self.session.add(county)
        await self.session.flush()
        feed = SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label="varazdinska", scope="county",
                          feed_url="http://burzarada.hzz.hr/rss/varazdinska.xml")
        self.session.add(feed)
        await self.session.flush()
        normalizer = JobConditionsNormalizer()
        self.pages: dict[str, RawJobConditionsDTO] = {}
        self.ids: dict[str, int] = {}
        for key, page, values in (
            ("cook", RawJobConditionsDTO(
                experience="1 godinu", employment_type="Na neodređeno; Novootvoreni poslovi",
                working_hours="Puno radno vrijeme", education="Srednja škola 3 godine; Srednja škola 4 godine",
                accommodation="Zajednički smještaj"),
             dict(page_valid_until=self.today + timedelta(days=5), deadline_on=self.today + timedelta(days=2),
                  page_work_place="VARAŽDIN, VARAŽDINSKA ŽUPANIJA", page_employer_name="RESTORAN d.o.o.",
                  category="UGOSTITELJI, RADNICI U TURIZMU", category_source="description")),
            # A trainee ad without a contract, part-time and expired yesterday.
            ("waiter", RawJobConditionsDTO(
                experience="Traži se pripravnik", employment_type="Novootvoreni poslovi",
                working_hours="20 sati tjedno",
                education="Srednja škola 4 godine; Viša ili prvostupanjska; Fakultet, akademija, magisterij, doktorat",
                accommodation="Nema smještaja"),
             dict(page_valid_until=self.today - timedelta(days=1))),
            # The page states neither the experience nor the type of employment, and an education it does not read.
            ("dishwasher", RawJobConditionsDTO(working_hours="Puno radno vrijeme", education="Po dogovoru"),
             dict(deadline_on=self.today)),
            # The same conditions as the cook, with the feed's deadline.
            ("baker", RawJobConditionsDTO(
                experience="1 godinu", employment_type="Na neodređeno", working_hours="Puno radno vrijeme",
                education="Srednja škola 4 godine; Srednja škola 3 godine", accommodation="Zajednički smještaj"),
             dict(deadline_on=self.today + timedelta(days=5))),
            # Pages never read, with and without a deadline from the feed.
            ("driver", None, dict(municipality="VARAŽDIN")),
            ("gone", None, dict(page_status="unavailable", page_checked_at=func.now(), deadline_on=self.today)),
        ):
            if page is not None:
                conditions = normalizer.normalize(page)
                values |= {"page_status": "fetched", "page_checked_at": func.now(), "page_fetched_at": func.now(),
                           "page_source_hash": key, **{f"page_{name}": value for name, value in page},
                           **{"conditions_unrecognised" if name == "unrecognised" else name: value
                              for name, value in conditions.model_dump(mode="json").items()}}
                self.pages[key] = page
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}", content_hash=key,
                      title=f"POSAO {key}", **values)
            self.session.add(job)
            await self.session.flush()
            self.ids[key] = job.id
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feed.id))
        await self.session.commit()
        self.service = JobSearchService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)),
                                        CroatianCountyCatalog(), comparator=JobComparator(JobConditionMatcher()))

    async def compare(self, *keys: str, conditions: JobComparisonConditionsDTO | None = None) -> JobComparisonDTO:
        return await self.service.compare_jobs([self.ids[key] for key in keys], conditions)

    @staticmethod
    def row(comparison: JobComparisonDTO, aspect: str) -> tuple[ComparisonCellDTO, ...]:
        return next(row.cells for row in comparison.rows if row.aspect == aspect)

    @staticmethod
    def column(comparison: JobComparisonDTO, index: int, field: str) -> dict[str, object]:
        """One job's field of every cell, by aspect."""
        return {row.aspect: getattr(row.cells[index], field) for row in comparison.rows}

    async def test_two_jobs_side_by_side_in_the_requested_order(self) -> None:
        comparison = await self.compare("waiter", "cook")
        self.assertEqual(comparison.today, self.today)
        self.assertEqual([job.id for job in comparison.jobs], [self.ids["waiter"], self.ids["cook"]])
        self.assertIsNone(comparison.conditions)
        cook = comparison.jobs[1]
        self.assertEqual((cook.display_title, cook.employer_name, cook.county_name, cook.display_location,
                          cook.canonical_url, cook.details_status, cook.category, cook.category_source),
                         ("POSAO cook", "RESTORAN d.o.o.", "Varaždinska županija", "VARAŽDIN, VARAŽDINSKA ŽUPANIJA",
                          "https://example.com/cook", "fetched", "UGOSTITELJI, RADNICI U TURIZMU", "description"))
        self.assertEqual((cook.conditions.experience_months, cook.conditions.contract), (12, "permanent"))
        self.assertEqual([row.aspect for row in comparison.rows], ASPECTS)
        for row in comparison.rows:
            self.assertEqual([cell.job_id for cell in row.cells], [self.ids["waiter"], self.ids["cook"]])
            self.assertIsNone(row.condition)
            self.assertEqual({(cell.verdict, cell.reason) for cell in row.cells}, {(None, None)})
            self.assertTrue(row.differs)
        self.assertEqual(self.column(comparison, 0, "value"), {
            "experience": "trainee ad",
            "education": "secondary school (4 years) or higher levels",
            "contract": None,
            "working_time": "part time, 20 h a week",
            "accommodation": "no accommodation",
            "deadline": f"expired on {self.today - timedelta(days=1)}",
        })
        # The job page's deadline comes before the feed's.
        self.assertEqual(self.column(comparison, 1, "value"), {
            "experience": "12 months",
            "education": "secondary school (3 years) or secondary school (4 years)",
            "contract": "permanent",
            "working_time": "full time",
            "accommodation": "shared accommodation",
            "deadline": f"open until {self.today + timedelta(days=5)} (5 days left)",
        })

    async def test_evidence_is_the_stored_page_text(self) -> None:
        comparison = await self.compare("cook", "waiter", "dishwasher")
        for index, key in enumerate(("cook", "waiter", "dishwasher")):
            with self.subTest(job=key):
                evidence = self.column(comparison, index, "evidence")
                self.assertEqual({aspect: evidence[aspect] for aspect in EVIDENCE_FIELDS},
                                 {aspect: getattr(self.pages[key], field) for aspect, field in EVIDENCE_FIELDS.items()})
        self.assertEqual([cell.evidence for cell in self.row(comparison, "deadline")], [
            f"{self.today + timedelta(days=5)}, from the job page",
            f"{self.today - timedelta(days=1)}, from the job page",
            f"{self.today}, from the HZZ feed",
        ])
        self.assertEqual(self.row(comparison, "experience")[0].evidence, "1 godinu")

    async def test_conditions_get_a_verdict_and_a_reason_from_the_job_data(self) -> None:
        comparison = await self.compare("cook", "waiter", "driver", conditions=WANTED)
        self.assertEqual(comparison.conditions, WANTED)
        self.assertEqual([row.condition for row in comparison.rows], [6, "secondary_4", "permanent", True, True, None])
        verdicts = {row.aspect: [cell.verdict for cell in row.cells] for row in comparison.rows}
        self.assertEqual(verdicts, {
            "experience": ["no_match", "match", "unknown"],
            "education": ["match", "match", "unknown"],
            "contract": ["match", "unknown", "unknown"],
            "working_time": ["match", "no_match", "unknown"],
            "accommodation": ["match", "no_match", "unknown"],
            "deadline": [None, None, None],
        })
        self.assertEqual(self.column(comparison, 0, "reason"), {
            "experience": "the job asks for 12 months of experience; you have 6 months",
            "education": "the job page lists secondary school (4 years) among the accepted levels",
            "contract": "the job's contract is permanent, as you want",
            "working_time": "the job is full time, as you want",
            "accommodation": "the job offers shared accommodation",
            "deadline": None,
        })
        self.assertEqual(self.column(comparison, 1, "reason"), {
            "experience": "the job is a trainee ad, which asks for no experience",
            "education": "the job page lists secondary school (4 years) among the accepted levels",
            "contract": "the job page states the type of employment but not the contract",
            "working_time": "the job is part time (20 h a week); you want full time",
            "accommodation": "the job offers no accommodation; you want some",
            "deadline": None,
        })
        # The page was never read: every value is unknown, and so is every verdict.
        self.assertEqual(comparison.jobs[2].conditions, None)
        self.assertEqual(comparison.jobs[2].details_status, "pending")
        for field, expected in (("value", None), ("evidence", None), ("verdict", "unknown"), ("reason", UNREAD)):
            column = self.column(comparison, 2, field)
            self.assertEqual({aspect: column[aspect] for aspect in EVIDENCE_FIELDS}, dict.fromkeys(EVIDENCE_FIELDS,
                                                                                                    expected))

    async def test_unknown_values_say_why(self) -> None:
        conditions = JobComparisonConditionsDTO(max_experience_months=0, contract="fixed_term", full_time=False,
                                                education="university", accommodation=False)
        comparison = await self.compare("dishwasher", "gone", "waiter", conditions=conditions)
        self.assertEqual(self.column(comparison, 0, "verdict"), {
            "experience": "unknown", "education": "unknown", "contract": "unknown", "working_time": "no_match",
            "accommodation": "unknown", "deadline": None,
        })
        self.assertEqual(self.column(comparison, 0, "reason"), {
            "experience": "the job page does not state the experience",
            "education": "the job page states the education in a way that could not be read",
            "contract": "the job page does not state the contract",
            "working_time": "the job is full time; you want part time",
            "accommodation": "the job page does not state the accommodation",
            "deadline": None,
        })
        # HZZ did not return the page.
        self.assertEqual(set(self.column(comparison, 1, "reason").values()),
                         {"HZZ did not return the job's page, so its conditions are unknown", None})
        self.assertEqual(self.column(comparison, 2, "reason"), {
            "experience": "the job is a trainee ad, which asks for no experience",
            "education": "the job page lists university degree among the accepted levels",
            "contract": "the job page states the type of employment but not the contract",
            "working_time": "the job is part time (20 h a week), as you want",
            "accommodation": "the job offers no accommodation, as you want",
            "deadline": None,
        })
        no_match = await self.compare("cook", "waiter", conditions=JobComparisonConditionsDTO(
            education="primary", accommodation=False, contract="other", max_experience_months=0))
        self.assertEqual(self.column(no_match, 0, "reason"), {
            "experience": "the job asks for 12 months of experience; you have none",
            "education": "the job page asks for secondary school (3 years) or secondary school (4 years), not primary "
                         "school",
            "contract": "the job's contract is permanent; you want another form of work",
            "working_time": None,
            "accommodation": "the job offers shared accommodation; you want a job without accommodation",
            "deadline": None,
        })
        self.assertEqual(self.row(no_match, "education")[1].reason,
                         "the job page asks for secondary school (4 years) or higher levels, not primary school")

    async def test_a_page_read_once_keeps_its_conditions_after_a_failed_fetch(self) -> None:
        # The search filters still use the stored conditions, so the comparison and the cards must too.
        await self.session.execute(update(Job).where(Job.id == self.ids["baker"]).values(page_status="failed"))
        await self.session.commit()
        conditions = JobComparisonConditionsDTO(contract="permanent")
        comparison = await self.compare("baker", "cook", conditions=conditions)
        self.assertEqual(self.row(comparison, "contract")[0].verdict, "match")
        self.assertEqual(self.row(comparison, "contract")[0].evidence, "Na neodređeno")
        self.assertIsNotNone(comparison.jobs[0].conditions)
        found = await self.service.search_cards(JobSearchFiltersDTO(contract="permanent"))
        baker = next(job for job in found.jobs if job.id == self.ids["baker"])
        self.assertEqual(baker.conditions.contract, "permanent")

    async def test_differs_compares_the_values_with_unknown_as_a_value_of_its_own(self) -> None:
        def differs(comparison: JobComparisonDTO) -> dict[str, bool]:
            return {row.aspect: row.differs for row in comparison.rows}

        # The baker states the cook's conditions, its education levels in another order.
        self.assertEqual(differs(await self.compare("cook", "baker")), {
            "experience": False, "education": False, "contract": False, "working_time": False,
            "accommodation": False, "deadline": False,
        })
        # Two unknown values are equal; an unknown deadline differs from a known one.
        self.assertEqual(differs(await self.compare("driver", "gone")), {
            "experience": False, "education": False, "contract": False, "working_time": False,
            "accommodation": False, "deadline": True,
        })
        # A known value differs from an unknown one.
        self.assertEqual(differs(await self.compare("cook", "baker", "driver")), dict.fromkeys(ASPECTS, True))
        self.assertEqual(differs(await self.compare("cook", "dishwasher")), {
            "experience": True, "education": True, "contract": True, "working_time": False,
            "accommodation": True, "deadline": True,
        })

    async def test_deadlines_open_expired_last_day_and_unknown(self) -> None:
        comparison = await self.compare("baker", "dishwasher", "driver")
        self.assertEqual([cell.value for cell in self.row(comparison, "deadline")], [
            f"open until {self.today + timedelta(days=5)} (5 days left)", f"open until {self.today} (last day)", None,
        ])
        self.assertEqual(self.row(comparison, "deadline")[2].evidence, None)
        # Conditions give the deadline no verdict.
        with_conditions = await self.compare("baker", "dishwasher", "driver", conditions=WANTED)
        self.assertEqual(self.row(with_conditions, "deadline"), self.row(comparison, "deadline"))

    async def test_conditions_without_a_value_are_no_conditions(self) -> None:
        comparison = await self.compare("cook", "waiter", conditions=JobComparisonConditionsDTO())
        self.assertEqual(comparison, await self.compare("cook", "waiter"))
        self.assertIsNone(comparison.conditions)
        # One condition gives verdicts on its aspect only.
        experience = await self.compare("cook", "waiter", conditions=JobComparisonConditionsDTO(
            max_experience_months=12))
        self.assertEqual({row.aspect: [cell.verdict for cell in row.cells] for row in experience.rows
                          if row.condition is not None}, {"experience": ["match", "match"]})
        self.assertEqual(sum(cell.verdict is not None for row in experience.rows for cell in row.cells), 2)

    async def test_two_or_three_distinct_existing_jobs(self) -> None:
        cook, waiter, driver, gone = (self.ids[key] for key in ("cook", "waiter", "driver", "gone"))
        for job_ids in ([cook], [], [cook, waiter, driver, gone]):
            with self.subTest(job_ids=job_ids), self.assertRaises(InvalidJobSearchError) as raised:
                await self.service.compare_jobs(job_ids)
            self.assertEqual(raised.exception.details, f"Choose 2 or 3 jobs to compare, not {len(job_ids)}.")
        for job_ids in ([cook, cook], [cook, waiter, cook]):
            with self.subTest(job_ids=job_ids), self.assertRaises(InvalidJobSearchError) as raised:
                await self.service.compare_jobs(job_ids)
            self.assertEqual(raised.exception.details,
                             f"Choose different jobs to compare; given more than once: {cook}.")
        missing = max(self.ids.values()) + 1
        for job_ids, message in (
            ([cook, missing], f"Job {missing} not found."),
            ([missing, cook, missing + 1], f"Jobs {missing}, {missing + 1} not found."),
            # IDs no job can have are not found either.
            ([0, cook, 2**63], "Jobs 0, 9223372036854775808 not found."),
        ):
            with self.subTest(job_ids=job_ids), self.assertRaises(NotFoundError) as raised:
                await self.service.compare_jobs(job_ids)
            self.assertEqual(raised.exception.details, message)
        # Three jobs, one of them no longer listed.
        await self.session.execute(text("UPDATE job_feed_memberships SET presence_status = 'missing', "
                                        "missing_since_at = now() WHERE job_id = :id"), {"id": gone})
        await self.session.commit()
        comparison = await self.service.compare_jobs((gone, driver, cook))
        self.assertEqual([job.id for job in comparison.jobs], [gone, driver, cook])
        self.assertEqual(comparison.jobs[0].county_name, "Varaždinska županija")
        self.assertEqual({len(row.cells) for row in comparison.rows}, {3})
