from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, SourceFeed


class SourceFeedModelTests(ModelTestCase):
    def feed(self, **overrides: object) -> SourceFeed:
        values = {
            "ckan_resource_id": uuid4(),
            "label": "Poslovi u EU",
            "feed_url": f"https://example.com/{uuid4()}.xml",
            "scope": "eu",
        }
        return SourceFeed(**(values | overrides))

    async def test_eu_feed_has_no_county_or_previous_sync(self) -> None:
        feed = self.feed()
        self.session.add(feed)
        await self.session.flush()
        self.assertTrue(feed.enabled)
        self.assertIsNone(feed.county_id)
        self.assertIsNone(feed.last_success_at)
        await self.assert_rejected(self.feed(scope="county"))
        await self.assert_rejected(self.feed(scope="unknown"))

    async def test_county_relationship_and_restricted_delete(self) -> None:
        county = County(code="zagreb", name="Grad Zagreb")
        feed = self.feed(scope="county", county=county)
        self.session.add(feed)
        await self.session.flush()
        loaded = await self.session.scalar(
            select(County).options(selectinload(County.source_feeds))
        )
        self.assertEqual(loaded.source_feeds, [feed])
        await self.assert_rejected(self.feed(county_id=county.id))
        await self.assert_rejected(self.feed(scope="county", county_id=9999))
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.delete(loaded)
                await self.session.flush()

    async def test_resource_id_and_feed_url_are_unique(self) -> None:
        feed = self.feed()
        self.session.add(feed)
        await self.session.flush()
        await self.assert_rejected(self.feed(ckan_resource_id=feed.ckan_resource_id))
        await self.assert_rejected(self.feed(feed_url=feed.feed_url))

    async def test_last_success_requires_a_check_at_or_after_it(self) -> None:
        now = datetime.now(timezone.utc)
        await self.assert_rejected(self.feed(last_success_at=now))
        await self.assert_rejected(
            self.feed(last_success_at=now, last_checked_at=now - timedelta(seconds=1))
        )

    async def test_occupation_feed_has_no_county(self) -> None:
        feed = self.feed(scope="occupation", label="Zanimanje")
        self.session.add(feed)
        await self.session.flush()
        self.assertIsNone(feed.county_id)
        county = County(code="zagreb", name="Grad Zagreb")
        self.session.add(county)
        await self.session.flush()
        await self.assert_rejected(self.feed(scope="occupation", county_id=county.id))
