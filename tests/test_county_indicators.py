from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, text, update

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, DzsImport, DzsImportFile, DzsIndicatorValue, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.county_indicators import CountyComparisonRequestDTO, UnemploymentHistoryRequestDTO
from FOIHireloom.dto.job_market import JobCountFiltersDTO
from FOIHireloom.exceptions import InvalidIndicatorRequestError, InvalidJobSearchError
from FOIHireloom.services import CountyIndicatorService, CroatianCountyCatalog

AUG, SEP = date(2026, 8, 1), date(2026, 9, 1)
T1_URL = "https://podaci.dzs.hr/media/ulbjlyex/rad-2026-2-6_3_tablice-hr.xlsx"
WORKBOOK_URL = "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx"


def months(first: date, last: date) -> list[date]:
    result = [first]
    while result[-1] < last:
        previous = result[-1]
        result.append(date(previous.year + previous.month // 12, previous.month % 12 + 1, 1))
    return result


class CountyDataTestCase(ModelTestCase):
    """Three counties: Varaždinska with four ads, Međimurska with one whose page omits the
    number of workers, and Istarska whose feed was never loaded; add_dzs() adds DZS values."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.today = await self.session.scalar(text("SELECT (now() AT TIME ZONE 'Europe/Zagreb')::date"))
        counties = {code: County(code=code, iso_code=iso_code, name=name) for code, iso_code, name in (
            ("varazdinska", "HR-05", "Varaždinska županija"), ("medimurska", "HR-20", "Međimurska županija"),
            ("istarska", "HR-18", "Istarska županija"))}
        self.session.add_all(counties.values())
        await self.session.flush()
        self.county_ids = {code: county.id for code, county in counties.items()}
        feeds = {
            code: SourceFeed(county_id=county.id, ckan_resource_id=uuid4(), label=code, scope="county",
                             feed_url=f"http://burzarada.hzz.hr/rss/{code}.xml",
                             last_checked_at=func.now(),
                             last_success_at=None if code == "istarska" else func.now())
            for code, county in counties.items()
        }
        self.session.add_all(feeds.values())
        await self.session.flush()
        self.feed_ids = {code: feed.id for code, feed in feeds.items()}
        page = {"page_status": "fetched", "page_checked_at": func.now(), "page_fetched_at": func.now()}
        for key, county, values in (
            ("cook", "varazdinska", dict(title="KUHAR/ICA", page_workers_needed=3, contract="permanent",
                                         page_valid_until=self.today + timedelta(days=2), **page)),
            # The page was not read: workers and contract are unknown.
            ("cook_unread", "varazdinska", dict(title="KUHAR", deadline_on=self.today + timedelta(days=30))),
            ("driver", "varazdinska", dict(title="VOZAČ", page_workers_needed=2, contract="permanent",
                                           page_valid_until=self.today + timedelta(days=20), **page)),
            ("cook_expired", "varazdinska", dict(title="KUHAR", page_workers_needed=5, contract="fixed_term",
                                                 page_valid_until=self.today - timedelta(days=1), **page)),
            ("waiter", "medimurska", dict(title="KONOBAR", contract="fixed_term", **page)),
        ):
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}",
                      content_hash=key, page_source_hash=key if "page_status" in values else None, **values)
            self.session.add(job)
            await self.session.flush()
            self.session.add(JobFeedMembership(job_id=job.id, feed_id=feeds[county].id))
        await self.session.commit()
        self.service = CountyIndicatorService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)),
                                              CroatianCountyCatalog())

    async def add_dzs(self) -> int:
        """A succeeded import with the DZS values the tests compare."""
        run = DzsImport(status="succeeded", finished_at=func.now(), values_inserted=0, values_updated=0,
                        values_unchanged=0)
        self.session.add(run)
        await self.session.flush()
        self.session.add_all([
            DzsImportFile(import_id=run.id, role=role, location=location, sheets=[], sha256="0" * 64, size_bytes=1,
                          fetched_at=func.now())
            for role, location in (("t1", T1_URL), ("workbook", WORKBOOK_URL))
        ])
        vz, md, ist = (self.county_ids[code] for code in ("varazdinska", "medimurska", "istarska"))
        rows = [
            # Međimurska has no exact count for September, so the common month of unemployed is August.
            (vz, "unemployed", AUG, "total", 1800, False, "t1"), (vz, "unemployed", SEP, "total", 1721, False, "t1"),
            (md, "unemployed", AUG, "total", 1500, False, "t1"), (md, "unemployed", SEP, "total", None, False, "t1"),
            (ist, "unemployed", SEP, "total", 900, False, "t1"),
            (vz, "active_population", SEP, "total", 2000, True, "t1"),
            (md, "active_population", SEP, "total", 1000, True, "t1"),
            (ist, "active_population", SEP, "total", 3000, True, "t1"),
            (vz, "unemployment_rate", SEP, "total", Decimal("2.3"), True, "t1"),
        ]
        # Monthly rates since January 2025; Međimurska lacks August 2025 and September 2026.
        for period in months(date(2025, 1, 1), AUG):
            rate = Decimal("2.9") if period == date(2025, 9, 1) else Decimal("2.5")
            rows.append((vz, "unemployment_rate", period, "total", rate, period.year == 2026, "workbook_9_4_14"))
            rows.append((vz, "unemployment_rate", period, "women", Decimal("3.4"), period.year == 2026,
                         "workbook_9_4_14"))
            if period != date(2025, 8, 1):
                rows.append((md, "unemployment_rate", period, "total", Decimal("4.0"), period.year == 2026,
                             "workbook_9_4_14"))
        rows.append((vz, "unemployment_rate", SEP, "women", Decimal("3.0"), True, "t1"))
        rows.append((vz, "unemployment_rate", SEP, "men", Decimal("1.9"), True, "workbook_9_4_14"))
        self.session.add_all([
            DzsIndicatorValue(county_id=county_id, indicator=indicator, period=period, sex=sex,
                              value=None if value is None else Decimal(value),
                              missing_reason="not_available" if value is None else None, is_provisional=provisional,
                              source=source, import_id=run.id)
            for county_id, indicator, period, sex, value, provisional, source in rows
        ])
        await self.session.commit()
        return run.id

    async def compare(self, *counties: str, period: date | str | None = None, **filters: object):
        return await self.service.compare_counties(CountyComparisonRequestDTO(
            counties=counties, filters=JobCountFiltersDTO(**filters), period=period))

    async def history(self, *counties: str, **values: object):
        return await self.service.unemployment_history(UnemploymentHistoryRequestDTO(counties=counties, **values))


class CountyIndicatorServiceTests(CountyDataTestCase):
    @staticmethod
    def counts(counts) -> tuple:
        return (counts.jobs, counts.workers_needed, counts.workers_needed_coverage.part,
                counts.permanent_share.part, counts.permanent_share.whole, counts.contract_coverage.part,
                counts.closing_soon)

    async def test_each_indicator_uses_the_latest_month_known_for_every_county(self) -> None:
        import_id = await self.add_dzs()
        result = await self.compare("varazdinska", "Međimurska županija")
        self.assertEqual({(p.indicator, p.period, p.requested, p.unavailable_reason) for p in result.dzs_periods},
                         {("unemployed", AUG, False, None), ("active_population", SEP, False, None),
                          ("unemployment_rate", AUG, False, None)})
        vz, md = result.counties
        self.assertEqual((vz.code, md.code), ("varazdinska", "medimurska"))
        self.assertEqual((vz.unemployed.value, vz.unemployed.period, vz.unemployed.is_provisional), (1800, AUG, False))
        self.assertEqual((vz.active_population.value, vz.active_population.is_provisional), (2000, True))
        self.assertEqual((vz.unemployment_rate.value, md.unemployment_rate.value), (Decimal("2.5"), Decimal("4.0")))
        # 1800 unemployed per 5 workers stated by 2 of the 3 active ads; 3 active ads per 2000 active.
        self.assertEqual(self.counts(vz.all_active_jobs), (3, 5, 2, 2, 2, 2, 1))
        self.assertEqual(vz.all_active_jobs.workers_needed_coverage.percent, Decimal("66.7"))
        self.assertEqual((vz.unemployed_per_worker.value, vz.unemployed_per_worker.numerator,
                          vz.unemployed_per_worker.denominator, vz.unemployed_per_worker.dzs_period),
                         (Decimal("360.0"), 1800, 5, AUG))
        self.assertEqual((vz.jobs_per_1000_active.value, vz.jobs_per_1000_active.numerator,
                          vz.jobs_per_1000_active.denominator, vz.jobs_per_1000_active.is_provisional),
                         (Decimal("1.5"), 3, 2000, True))
        # Međimurska's one ad does not state the number of workers, which is unknown, not 0.
        self.assertEqual((md.unemployed_per_worker.value, md.unemployed_per_worker.numerator,
                          md.unemployed_per_worker.denominator, md.unemployed_per_worker.unavailable_reason),
                         (None, 1500, None, "no_known_workers"))
        self.assertEqual(md.jobs_per_1000_active.value, Decimal("1.0"))
        self.assertEqual((result.dzs.import_id, [file.role for file in result.dzs.files]), (import_id, ["t1", "workbook"]))
        self.assertEqual([(source.name, source.url) for source in result.sources],
                         [("HZZ", "https://burzarada.hzz.hr"), ("DZS release table T1", T1_URL),
                          ("DZS county workbook", WORKBOOK_URL)])
        self.assertEqual(result.hzz_coverage.data_status, "fresh")
        self.assertIsNotNone(result.hzz_coverage.data_as_of)
        self.assertEqual(len(result.notes), 5)

    async def test_a_requested_month_is_never_replaced_by_another(self) -> None:
        await self.add_dzs()
        result = await self.compare("varazdinska", "medimurska", period="2026-09")
        self.assertTrue(all(p.requested and p.period == SEP for p in result.dzs_periods))
        vz, md = result.counties
        self.assertEqual((vz.unemployed.value, vz.unemployed_per_worker.value), (1721, Decimal("344.2")))
        # DZS marked Međimurska's September count as not available; August is not used instead.
        self.assertEqual((md.unemployed.value, md.unemployed.period, md.unemployed.unavailable_reason,
                          md.unemployed.missing_reason), (None, SEP, "dzs_value_missing", "not_available"))
        self.assertEqual((md.unemployed_per_worker.value, md.unemployed_per_worker.unavailable_reason),
                         (None, "dzs_value_missing"))
        # A month without any stored row.
        july = await self.compare("varazdinska", "medimurska", period=date(2026, 7, 1))
        for county in july.counties:
            self.assertEqual((county.unemployed.value, county.unemployed.period, county.unemployed.unavailable_reason,
                              county.unemployed.missing_reason), (None, date(2026, 7, 1), "dzs_value_missing", None))
            self.assertEqual(county.jobs_per_1000_active.unavailable_reason, "dzs_value_missing")

    async def test_filters_choose_the_filtered_counts_but_never_the_indicators(self) -> None:
        await self.add_dzs()
        everything = await self.compare("varazdinska", "medimurska")
        cooks = await self.compare("varazdinska", "medimurska", query="kuhari")
        vz = cooks.counties[0]
        self.assertEqual(self.counts(vz.filtered_jobs), (2, 3, 1, 1, 1, 1, 1))
        self.assertEqual((vz.filtered_jobs.permanent_share.percent, vz.filtered_jobs.contract_coverage.percent),
                         (Decimal("100.0"), Decimal("50.0")))
        self.assertEqual(vz.all_active_jobs, everything.counties[0].all_active_jobs)
        self.assertEqual((vz.unemployed_per_worker, vz.jobs_per_1000_active),
                         (everything.counties[0].unemployed_per_worker, everything.counties[0].jobs_per_1000_active))
        self.assertEqual(cooks.filters.query, "kuhari")
        # Expired ads count only in the filtered counts, and only when asked for.
        expired = (await self.compare("varazdinska", "medimurska", query="kuhar", include_expired=True)).counties[0]
        self.assertEqual((expired.filtered_jobs.jobs, expired.all_active_jobs.jobs), (3, 3))
        # No matching ad is an empty result from a county whose data is there.
        nothing = (await self.compare("varazdinska", "medimurska", query="pilot")).counties[1]
        self.assertEqual((nothing.filtered_jobs.jobs, nothing.filtered_jobs.workers_needed_coverage.percent,
                          nothing.hzz_data_status), (0, None, "fresh"))

    async def test_unknown_hzz_data_and_zero_denominators_are_unavailable(self) -> None:
        await self.add_dzs()
        istria = (await self.compare("varazdinska", "istarska", period=SEP)).counties[1]
        # The feed was never loaded, so Istria's 0 ads are not known to be 0.
        self.assertEqual((istria.hzz_data_status, istria.hzz_last_success_at, istria.all_active_jobs.jobs),
                         ("unavailable", None, 0))
        self.assertEqual((istria.unemployed_per_worker.unavailable_reason, istria.unemployed_per_worker.denominator,
                          istria.jobs_per_1000_active.unavailable_reason, istria.jobs_per_1000_active.numerator),
                         ("no_hzz_data", None, "no_hzz_data", None))
        await self.session.execute(update(SourceFeed).where(SourceFeed.id == self.feed_ids["istarska"]).values(
            last_checked_at=func.now(), last_success_at=func.now()))
        await self.session.commit()
        istria = (await self.compare("varazdinska", "istarska", period=SEP)).counties[1]
        # Loaded and empty: no workers sought, so the ratio has a zero denominator; 0 ads per 1000 is a value.
        self.assertEqual((istria.unemployed_per_worker.value, istria.unemployed_per_worker.denominator,
                          istria.unemployed_per_worker.unavailable_reason), (None, 0, "zero_denominator"))
        self.assertEqual((istria.jobs_per_1000_active.value, istria.jobs_per_1000_active.unavailable_reason),
                         (Decimal("0.0"), None))
        await self.session.execute(update(DzsIndicatorValue).where(
            DzsIndicatorValue.county_id == self.county_ids["istarska"],
            DzsIndicatorValue.indicator == "active_population").values(value=0))
        await self.session.commit()
        istria = (await self.compare("varazdinska", "istarska", period=SEP)).counties[1]
        self.assertEqual((istria.jobs_per_1000_active.value, istria.jobs_per_1000_active.denominator,
                          istria.jobs_per_1000_active.unavailable_reason), (None, 0, "zero_denominator"))

    async def test_without_a_dzs_import_the_hzz_counts_still_come(self) -> None:
        result = await self.compare("varazdinska", "medimurska", query="kuhar")
        self.assertIsNone(result.dzs)
        self.assertEqual([source.name for source in result.sources], ["HZZ"])
        self.assertTrue(all(p.period is None and p.unavailable_reason == "no_dzs_data" for p in result.dzs_periods))
        vz = result.counties[0]
        self.assertEqual((vz.filtered_jobs.jobs, vz.all_active_jobs.jobs, vz.all_active_jobs.workers_needed), (2, 3, 5))
        for value in (vz.unemployed, vz.active_population, vz.unemployment_rate):
            self.assertEqual((value.value, value.period, value.unavailable_reason), (None, None, "no_dzs_data"))
        self.assertEqual((vz.unemployed_per_worker.value, vz.unemployed_per_worker.denominator,
                          vz.unemployed_per_worker.unavailable_reason), (None, 5, "no_dzs_data"))
        self.assertEqual((vz.jobs_per_1000_active.numerator, vz.jobs_per_1000_active.unavailable_reason),
                         (3, "no_dzs_data"))
        history = await self.history("varazdinska")
        self.assertEqual((history.unavailable_reason, history.last_period, history.counties[0].series,
                          history.counties[0].change_unavailable_reason), ("no_dzs_data", None, (), "no_dzs_data"))

    async def test_the_latest_succeeded_import_is_the_provenance(self) -> None:
        succeeded = await self.add_dzs()
        failed = DzsImport(status="failed", finished_at=func.now(), error_summary="DZS returned HTTP 503.")
        self.session.add(failed)
        await self.session.commit()
        result = await self.compare("varazdinska", "medimurska")
        self.assertEqual(result.dzs.import_id, succeeded)
        self.assertEqual({file.location for file in result.dzs.files}, {T1_URL, WORKBOOK_URL})

    async def test_counties_and_month_are_checked(self) -> None:
        for counties, message in (
            (("varazdinska",), "Choose 2 to 6 counties, not 1"),
            (("varazdinska",) * 7, "Choose 2 to 6 counties, not 7"),
            (("varazdinska", "Atlantida"), "Unknown county: Atlantida. Use county codes or names from list_regions: "
                                           "istarska, medimurska, varazdinska."),
            (("varazdinska", "Varaždinska županija"), "given more than once: varazdinska"),
            # A county the catalogue knows but the database does not.
            (("varazdinska", "zadarska"), "Unknown county: zadarska"),
        ):
            with self.subTest(counties=counties), self.assertRaisesRegex(InvalidIndicatorRequestError, message):
                await self.compare(*counties)
        with self.assertRaisesRegex(InvalidJobSearchError, "no searchable words"):
            await self.compare("varazdinska", "medimurska", query="--")
        with self.assertRaisesRegex(InvalidIndicatorRequestError, "Choose 1 to 6 counties, not 0"):
            await self.history()
        for period in ("2026-13", "2026-9", "septembar", date(2026, 9, 2)):
            with self.subTest(period=period), self.assertRaises(ValidationError):
                CountyComparisonRequestDTO(counties=("a", "b"), period=period)
        for months_ in (11, 25):
            with self.subTest(months=months_), self.assertRaises(ValidationError):
                UnemploymentHistoryRequestDTO(counties=("a",), months=months_)

    async def test_history_ends_with_the_latest_month_known_for_every_county(self) -> None:
        await self.add_dzs()
        result = await self.history("varazdinska")
        varazdinska = result.counties[0]
        self.assertEqual((result.first_period, result.last_period, result.sex, result.months),
                         (date(2025, 10, 1), SEP, "total", 12))
        self.assertEqual([p.period for p in varazdinska.series], months(date(2025, 10, 1), SEP))
        self.assertEqual((varazdinska.latest.rate, varazdinska.same_month_previous_year.rate, varazdinska.change_pp),
                         (Decimal("2.3"), Decimal("2.9"), Decimal("-0.6")))
        self.assertEqual(varazdinska.same_month_previous_year.period, date(2025, 9, 1))
        self.assertEqual([p.is_provisional for p in varazdinska.series], [False] * 3 + [True] * 9)
        self.assertEqual([source.name for source in result.sources], ["DZS release table T1", "DZS county workbook"])
        self.assertEqual(len(result.notes), 3)
        # Međimurska has no September rate, so both series end in August; its August 2025 is missing.
        both = await self.history("varazdinska", "medimurska")
        self.assertEqual(both.last_period, AUG)
        md = both.counties[1]
        self.assertEqual((md.latest.rate, md.same_month_previous_year.rate, md.same_month_previous_year.period,
                          md.same_month_previous_year.unavailable_reason, md.change_pp, md.change_unavailable_reason),
                         (Decimal("4.0"), None, date(2025, 8, 1), "dzs_value_missing", None, "dzs_value_missing"))
        self.assertEqual(both.counties[0].change_pp, Decimal("0.0"))

    async def test_history_window_and_sex(self) -> None:
        await self.add_dzs()
        long = (await self.history("varazdinska", months=24)).counties[0]
        self.assertEqual((len(long.series), long.series[0].period, long.series[-1].period),
                         (24, date(2024, 10, 1), SEP))
        # Months before the stored series are missing, not 0.
        self.assertEqual({(p.rate, p.is_provisional, p.unavailable_reason) for p in long.series[:3]},
                         {(None, None, "dzs_value_missing")})
        women = (await self.history("varazdinska", sex="women")).counties[0]
        self.assertEqual((women.latest.rate, women.same_month_previous_year.rate, women.change_pp),
                         (Decimal("3.0"), Decimal("3.4"), Decimal("-0.4")))
        men = await self.history("varazdinska", sex="men")
        self.assertEqual((men.last_period, men.counties[0].latest.rate, men.counties[0].change_unavailable_reason),
                         (SEP, Decimal("1.9"), "dzs_value_missing"))
        # Međimurska has no rate for men at all.
        nothing = await self.history("varazdinska", "medimurska", sex="men")
        self.assertEqual((nothing.unavailable_reason, nothing.counties[1].series), ("no_common_period", ()))
