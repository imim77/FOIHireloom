from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, text, update

from model_test_case import ModelTestCase

from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.dto.job_market import JobMarketCriteriaDTO

HOSPITALITY, HEALTH = "UGOSTITELJI", "ZDRAVSTVO"


class JobMarketRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.today = await self.session.scalar(text("SELECT (now() AT TIME ZONE 'Europe/Zagreb')::date"))
        counties = {code: County(code=code, name=name) for code, name in (("istarska", "Istarska županija"),
                                                                           ("grad-zagreb", "Grad Zagreb"))}
        self.session.add_all(counties.values())
        await self.session.flush()
        self.county_ids = {code: county.id for code, county in counties.items()}
        feeds = {
            name: SourceFeed(county_id=counties[code].id, ckan_resource_id=uuid4(), label=name, scope="county",
                             feed_url=f"http://burzarada.hzz.hr/rss/{name}.xml")
            for name, code in (("is1", "istarska"), ("is2", "istarska"), ("zg", "grad-zagreb"))
        }
        # Health jobs can be filled in from an occupation feed.
        health = SourceFeed(ckan_resource_id=uuid4(), label="Zdravstvo", scope="occupation",
                            feed_url="http://burzarada.hzz.hr/rss/health.xml")
        self.session.add_all([*feeds.values(), health])
        await self.session.flush()
        page = {"page_status": "fetched", "page_checked_at": func.now(), "page_fetched_at": func.now()}
        for key, values, listings in (
            ("cook", dict(title="KUHAR/ICA", category=HOSPITALITY, published_on=self.today - timedelta(days=1),
                          page_valid_until=self.today + timedelta(days=3), page_workers_needed=3,
                          page_employer_name="HOTEL d.o.o.", contract="permanent", employment_tags=["seasonal"],
                          full_time=True, education_levels=["secondary_3", "secondary_4"], experience_months=12,
                          trainee=False, accommodation="shared", schedule_tags=["morning", "two_shifts"],
                          transport_allowance="full", **page), {"is1": "present", "is2": "present"}),
            ("waiter", dict(title="KONOBAR", category=HOSPITALITY, published_on=self.today - timedelta(days=10),
                            page_valid_until=self.today + timedelta(days=20), page_workers_needed=2,
                            page_employer_name="HOTEL d.o.o.", contract="fixed_term", employment_tags=[],
                            full_time=False, weekly_hours=20, education_levels=["secondary_3"], experience_months=0,
                            trainee=False, accommodation="none", **page),
             {"is1": "present"}),
            ("nurse", dict(title="MEDICINSKA SESTRA", category=HEALTH, category_source="feed",
                           category_feed_id=health.id, published_on=self.today,
                           deadline_on=self.today + timedelta(days=1)), {"zg": "present"}),
            ("expired", dict(title="LIJEČNIK", category=HEALTH, published_on=self.today - timedelta(days=30),
                             page_valid_until=self.today - timedelta(days=1), page_workers_needed=5,
                             page_employer_name="BOLNICA", page_experience="", **page), {"zg": "present"}),
            ("gone", dict(title="KUHAR", category=HOSPITALITY, page_workers_needed=9, page_employer_name="HOTEL d.o.o.",
                          **page), {"is1": "missing"}),
        ):
            if "category" in values:
                values = {"category_source": "description"} | values
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}",
                      content_hash=key, page_source_hash=key if "page_status" in values else None, **values)
            self.session.add(job)
            await self.session.flush()
            for feed, status in listings.items():
                self.session.add(JobFeedMembership(job_id=job.id, feed_id=feeds[feed].id, presence_status=status,
                                                   missing_since_at=func.now() if status == "missing" else None))
        await self.session.commit()
        self.repository = SqlAlchemyJobRepository(self.session)

    async def aggregates(self, **criteria: object):
        values = {"open_on": self.today, "today": self.today, "top": 10} | criteria
        return await self.repository.market_aggregates(JobMarketCriteriaDTO(**values))

    @staticmethod
    def counts(items) -> list[tuple[str, int, int]]:
        return [(item.name, item.jobs, item.workers_needed) for item in items]

    async def test_counts_open_listed_jobs_by_field(self) -> None:
        stats = await self.aggregates()
        self.assertEqual((stats.jobs, stats.with_details, stats.with_category, stats.workers_needed), (3, 2, 3, 5))
        # The nurse's category was filled in from the occupation feed.
        self.assertEqual((stats.category_from_description, stats.category_from_feed), (2, 1))
        # The cook and the nurse were published within a week and close within a week.
        self.assertEqual((stats.published_recently, stats.closing_soon), (2, 2))
        # The cook is listed by two Istrian feeds but counts once.
        self.assertEqual([(county.code, county.name, county.jobs, county.workers_needed) for county in stats.counties],
                         [("istarska", "Istarska županija", 2, 5), ("grad-zagreb", "Grad Zagreb", 1, 0)])
        self.assertEqual(self.counts(stats.categories), [(HOSPITALITY, 2, 5), (HEALTH, 1, 0)])
        self.assertEqual(self.counts(stats.employers), [("HOTEL d.o.o.", 2, 5)])
        self.assertEqual(self.counts(stats.contracts), [("fixed_term", 1, 2), ("permanent", 1, 3)])
        # The waiter's empty tag list is known and adds nothing.
        self.assertEqual(self.counts(stats.employment_tags), [("seasonal", 1, 3)])
        self.assertEqual(self.counts(stats.education_levels), [("secondary_3", 2, 5), ("secondary_4", 1, 3)])
        self.assertEqual(self.counts(stats.working_time), [("full_time", 1, 3), ("part_time", 1, 2)])
        self.assertEqual({item.name: item.jobs for item in stats.experience_bands}, {"1_to_12_months": 1, "none": 1})
        self.assertEqual(self.counts(stats.accommodation), [("none", 1, 2), ("shared", 1, 3)])
        self.assertEqual(self.counts(stats.schedule_tags), [("morning", 1, 3), ("two_shifts", 1, 3)])
        # The waiter's page does not state the transport allowance.
        self.assertEqual(self.counts(stats.transport_allowance), [("full", 1, 3)])

    async def test_uses_the_search_filters(self) -> None:
        self.assertEqual((await self.aggregates(terms=("kuhar",))).jobs, 1)
        self.assertEqual((await self.aggregates(category="zdravstvo")).jobs, 1)
        # Expired jobs count only without open_on; unknown values are left out.
        zagreb = await self.aggregates(county_id=self.county_ids["grad-zagreb"], open_on=None)
        self.assertEqual((zagreb.jobs, zagreb.workers_needed), (2, 5))
        self.assertEqual([county.code for county in zagreb.counties], ["grad-zagreb"])
        self.assertEqual((zagreb.experience_bands, zagreb.contracts), ((), ()))
        nothing = await self.aggregates(terms=("pilot",))
        self.assertEqual((nothing.jobs, nothing.workers_needed, nothing.counties, nothing.employers), (0, 0, (), ()))

    async def test_categories_cover_only_jobs_that_state_one(self) -> None:
        await self.session.execute(update(Job).where(Job.source_job_id == "nurse").values(
            category=None, category_source=None, category_feed_id=None))
        await self.session.commit()
        stats = await self.aggregates()
        self.assertEqual((stats.jobs, stats.with_category, stats.category_from_description, stats.category_from_feed),
                         (3, 2, 2, 0))
        self.assertEqual(self.counts(stats.categories), [(HOSPITALITY, 2, 5)])

    async def test_top_limits_only_long_breakdowns(self) -> None:
        stats = await self.aggregates(top=1)
        self.assertEqual(len(stats.employers), 1)
        self.assertEqual((len(stats.categories), len(stats.contracts), len(stats.experience_bands)), (2, 2, 2))
