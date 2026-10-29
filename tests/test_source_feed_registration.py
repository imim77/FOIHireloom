import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import func, select

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, Job, SourceFeed, SyncRun
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.ckan import CkanResource
from FOIHireloom.exceptions import CkanError
from FOIHireloom.integrations.concrete.ckan import CkanClient
from FOIHireloom.services.source_feed_registration import (
    SourceFeedRegistrationError, SourceFeedRegistrationPlanner, SourceFeedRegistrationService,
)


class RegistrationPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads((Path(__file__).parent / "fixtures/ckan_package_show.json").read_text())
        self.planner = SourceFeedRegistrationPlanner()

    def build(self):
        return self.planner.build([CkanResource.model_validate(row) for row in self.payload["result"]["resources"]])

    def test_real_fixture_maps_all_counties_and_distinguishes_city_from_county(self) -> None:
        plan = self.build()
        self.assertEqual(len(plan.sources), 21)
        self.assertEqual(plan.resources_skipped, 1)
        self.assertEqual({source.county.code for source in plan.sources}, {c.code for c in self.planner.catalog.definitions})
        self.assertEqual(plan.sources[3].county.name, "Grad Zagreb")
        self.assertEqual(plan.sources[-1].county.name, "Zagrebačka županija")
        self.assertEqual(plan.sources[9].county.code, "medimurska")

    def test_labels_accept_case_spacing_accents_and_name_fallback(self) -> None:
        resource = self.payload["result"]["resources"][6]
        resource.update(description=" ", name="  koprivnicko – krizevacka ZUPANIJA ")
        self.assertEqual(self.build().sources[6].county.code, "koprivnicko-krizevacka")

    def test_inactive_and_non_feed_resources_are_skipped(self) -> None:
        resources = self.payload["result"]["resources"]
        resources.extend([
            dict(resources[0], id=str(uuid4()), state="deleted", description="Unknown"),
            dict(resources[0], id=str(uuid4()), format="PDF", description="Attachment"),
        ])
        plan = self.build()
        self.assertEqual(len(plan.sources), 21)
        self.assertEqual(plan.resources_skipped, 3)

    def test_unknown_active_county_label_is_not_guessed(self) -> None:
        self.payload["result"]["resources"][0]["description"] = "Unknown county"
        with self.assertRaisesRegex(SourceFeedRegistrationError, "Unrecognised"):
            self.build()

    def test_duplicate_ids_or_urls_are_rejected(self) -> None:
        for field in ("id", "url"):
            payload = copy.deepcopy(self.payload)
            payload["result"]["resources"][1][field] = payload["result"]["resources"][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(SourceFeedRegistrationError, "Duplicate"):
                self.planner.build([CkanResource.model_validate(row) for row in payload["result"]["resources"]])

    def test_empty_or_only_eu_resources_are_rejected(self) -> None:
        for resources in ([], [CkanResource.model_validate(self.payload["result"]["resources"][-1])]):
            with self.subTest(resources=resources), self.assertRaisesRegex(SourceFeedRegistrationError, "no supported"):
                self.planner.build(resources)


class SourceFeedRegistrationTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.payload = json.loads((Path(__file__).parent / "fixtures/ckan_package_show.json").read_text())
        self.status = 200
        self.sessions = SessionManager(self.engine)
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))
        self.addAsyncCleanup(self.http.aclose)
        self.service = SourceFeedRegistrationService(
            CkanClient(self.http, "https://ckan.example/ckan"),
            SqlAlchemyUnitOfWorkFactory(self.sessions),
        )

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.assertEqual(request.url.params["id"], "dataset")
        self.assertEqual(self.engine.pool.checkedout(), 0, "Network fetch must not hold a DB connection")
        return httpx.Response(self.status, json=self.payload)

    async def counts(self) -> tuple[int, int]:
        async with self.sessions.session() as reader:
            return (
                await reader.scalar(select(func.count(County.id))),
                await reader.scalar(select(func.count(SourceFeed.id))),
            )

    async def test_initial_registration_and_repeat_are_idempotent(self) -> None:
        result = await self.service.register_sources("dataset")
        self.assertEqual((result.counties_added, result.feeds_added, result.resources_skipped), (21, 21, 1))
        async with self.sessions.session() as reader:
            before = [(f.id, f.ckan_resource_id, f.county_id) for f in await reader.scalars(select(SourceFeed).order_by(SourceFeed.id))]
            self.assertTrue(all(f.scope == "county" and f.enabled for f in await reader.scalars(select(SourceFeed))))
            self.assertEqual(await reader.scalar(select(func.count(Job.id))), 0)
        result = await self.service.register_sources("dataset")
        self.assertEqual((result.counties_added, result.feeds_added, result.feeds_updated, result.feeds_unchanged), (0, 0, 0, 21))
        self.assertEqual(await self.counts(), (21, 21))
        async with self.sessions.session() as reader:
            self.assertEqual([(f.id, f.ckan_resource_id, f.county_id) for f in await reader.scalars(select(SourceFeed).order_by(SourceFeed.id))], before)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_existing_county_name_reuses_legacy_code_and_id(self) -> None:
        county = County(code="zagreb", name="Grad Zagreb")
        self.session.add(county)
        await self.session.commit()
        result = await self.service.register_sources("dataset")
        self.assertEqual(result.counties_added, 20)
        async with self.sessions.session() as reader:
            feed = await reader.scalar(select(SourceFeed).where(SourceFeed.label == "GRAD ZAGREB"))
            self.assertEqual(feed.county_id, county.id)
            self.assertEqual((await reader.get(County, county.id)).code, "zagreb")

    async def test_label_update_preserves_disabled_flag_validators_and_history(self) -> None:
        await self.service.register_sources("dataset")
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        async with self.sessions.session() as writer:
            feed = await writer.scalar(select(SourceFeed).order_by(SourceFeed.id))
            feed_id = feed.id
            feed.enabled, feed.etag = False, '"saved-etag"'
            feed.source_last_modified_at = feed.last_checked_at = feed.last_success_at = when
            record = SyncRun(feed_id=feed.id)
            writer.add(record)
            await writer.commit()
            run_id = record.id
        self.payload["result"]["resources"][0]["description"] = "Bjelovarsko-bilogorska županija"
        result = await self.service.register_sources("dataset")
        self.assertEqual((result.feeds_updated, result.feeds_unchanged), (1, 20))
        async with self.sessions.session() as reader:
            feed = await reader.get(SourceFeed, feed_id)
            self.assertFalse(feed.enabled)
            self.assertEqual(feed.etag, '"saved-etag"')
            self.assertEqual(feed.last_success_at, when)
            self.assertEqual(feed.source_last_modified_at, when)
            self.assertEqual((await reader.get(SyncRun, run_id)).feed_id, feed_id)

    async def test_url_change_clears_only_url_dependent_validators(self) -> None:
        await self.service.register_sources("dataset")
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        async with self.sessions.session() as writer:
            feed = await writer.scalar(select(SourceFeed).order_by(SourceFeed.id))
            feed_id = feed.id
            feed.etag, feed.source_last_modified_at, feed.last_checked_at = '"old"', when, when
            await writer.commit()
        self.payload["result"]["resources"][0]["url"] = "https://burzarada.hzz.hr/rss/moved.xml"
        result = await self.service.register_sources("dataset")
        self.assertEqual(result.feeds_updated, 1)
        async with self.sessions.session() as reader:
            feed = await reader.get(SourceFeed, feed_id)
            self.assertEqual(feed.feed_url, "https://burzarada.hzz.hr/rss/moved.xml")
            self.assertIsNone(feed.etag)
            self.assertIsNone(feed.source_last_modified_at)
            self.assertEqual(feed.last_checked_at, when)

    async def test_recreated_resource_uuid_reuses_existing_feed_url_and_database_id(self) -> None:
        await self.service.register_sources("dataset")
        async with self.sessions.session() as reader:
            feed_id = await reader.scalar(select(SourceFeed.id).order_by(SourceFeed.id))
        replacement_id = uuid4()
        self.payload["result"]["resources"][0]["id"] = str(replacement_id)
        result = await self.service.register_sources("dataset")
        self.assertEqual((result.feeds_added, result.feeds_updated), (0, 1))
        async with self.sessions.session() as reader:
            self.assertEqual((await reader.get(SourceFeed, feed_id)).ckan_resource_id, replacement_id)
        self.assertEqual(await self.counts(), (21, 21))

    async def test_conflicting_existing_resource_and_url_rolls_back_registration(self) -> None:
        await self.service.register_sources("dataset")
        original = copy.deepcopy(self.payload)
        resources = self.payload["result"]["resources"]
        resources[0]["url"] = resources[1]["url"]
        resources[1]["url"] = "https://example.com/new-location.xml"
        with self.assertRaisesRegex(SourceFeedRegistrationError, "different existing feeds"):
            await self.service.register_sources("dataset")
        async with self.sessions.session() as reader:
            urls = list(await reader.scalars(select(SourceFeed.feed_url).order_by(SourceFeed.id)))
        self.assertEqual(urls, [r["url"] for r in original["result"]["resources"][:-1]])

    async def test_database_conflict_rolls_back_new_counties_and_feeds(self) -> None:
        self.session.add(SourceFeed(
            ckan_resource_id=uuid4(), label="Legacy EU", scope="eu",
            feed_url=self.payload["result"]["resources"][0]["url"],
        ))
        await self.session.commit()
        with self.assertRaisesRegex(SourceFeedRegistrationError, "rolled back"):
            await self.service.register_sources("dataset")
        self.assertEqual(await self.counts(), (0, 1))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_upstream_and_mapping_errors_do_not_write_reference_data(self) -> None:
        original = copy.deepcopy(self.payload)
        for scenario in ("http", "action", "uuid", "label", "duplicate", "empty"):
            self.payload = copy.deepcopy(original)
            self.status = 503 if scenario == "http" else 200
            if scenario == "action":
                self.payload = {"success": False}
            elif scenario == "uuid":
                self.payload["result"]["resources"][0]["id"] = "invalid"
            elif scenario == "label":
                self.payload["result"]["resources"][0]["description"] = "Unknown"
            elif scenario == "duplicate":
                self.payload["result"]["resources"][1]["id"] = self.payload["result"]["resources"][0]["id"]
            elif scenario == "empty":
                self.payload["result"]["resources"] = []
            with self.subTest(scenario=scenario), self.assertRaises((CkanError, SourceFeedRegistrationError)):
                await self.service.register_sources("dataset")
            self.assertEqual(await self.counts(), (0, 0))

    async def test_conflicting_county_keys_preserve_existing_rows(self) -> None:
        self.session.add_all([
            County(code="legacy-zagreb", name="Grad Zagreb"),
            County(code="grad-zagreb", name="Conflicting name"),
        ])
        await self.session.commit()
        with self.assertRaisesRegex(SourceFeedRegistrationError, "different existing counties"):
            await self.service.register_sources("dataset")
        self.assertEqual(await self.counts(), (2, 0))

    async def test_disappearing_catalog_resource_is_not_deleted_or_disabled(self) -> None:
        await self.service.register_sources("dataset")
        self.payload["result"]["resources"].pop(0)
        result = await self.service.register_sources("dataset")
        self.assertEqual(result.feeds_unchanged, 20)
        self.assertEqual(await self.counts(), (21, 21))
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count(SourceFeed.id)).where(SourceFeed.enabled.is_(True))), 21)
