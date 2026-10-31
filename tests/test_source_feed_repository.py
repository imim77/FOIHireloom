from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.dto.source_feed import SourceFeedCreateDTO, SourceFeedDTO, SourceFeedUpdateDTO
from FOIHireloom.exceptions import NotFoundError
from FOIHireloom.dao.concrete.sqla_source_feed import SqlAlchemySourceFeedRepository
from FOIHireloom.dao.interfaces.source_feed import SourceFeedRepository


class SourceFeedRepositoryTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.county = County(code="zagreb", name="Grad Zagreb")
        self.session.add(self.county)
        await self.session.commit()
        self.county_id = self.county.id
        self.repository: SourceFeedRepository = SqlAlchemySourceFeedRepository(self.session)
        self.sessions = SessionManager(self.engine)

    def feed(self, **overrides: object) -> SourceFeed:
        values = {
            "county_id": self.county_id,
            "ckan_resource_id": uuid4(),
            "label": "Poslovi u Gradu Zagrebu",
            "feed_url": f"https://example.com/{uuid4()}.xml",
            "scope": "county",
        }
        return SourceFeed(**(values | overrides))

    async def test_add_flushes_defaults_without_committing(self) -> None:
        feed = self.feed()
        self.assertIsNone(await self.repository.add(feed))
        self.assertIsInstance(feed.id, int)
        self.assertTrue(feed.enabled)
        self.assertIsNone(feed.etag)
        self.assertIsNone(feed.last_checked_at)
        self.assertIsNone(feed.last_success_at)
        self.assertIs(await self.repository.get_by_id(feed.id), feed)
        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemySourceFeedRepository(reader).get_by_id(feed.id))

    async def test_explicit_commit_persists_feed_for_both_lookups(self) -> None:
        feed = self.feed()
        await self.repository.add(feed)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            saved = await repository.get_by_id(feed.id)
            self.assertIsNotNone(saved)
            self.assertIsNot(saved, feed)
            self.assertEqual(saved.ckan_resource_id, feed.ckan_resource_id)
            self.assertEqual(saved.county_id, self.county.id)
            self.assertEqual(saved.label, "Poslovi u Gradu Zagrebu")
            self.assertEqual(saved.feed_url, feed.feed_url)
            self.assertEqual(saved.scope, "county")
            self.assertIs(await repository.get_by_ckan_resource_id(feed.ckan_resource_id), saved)
            self.assertIs(await repository.get_by_feed_url(feed.feed_url), saved)

    async def test_missing_feeds_return_none_and_empty_list(self) -> None:
        self.assertEqual(await self.repository.list_enabled(), [])
        feed = self.feed()
        await self.repository.add(feed)
        self.assertIsNone(await self.repository.get_by_id(feed.id + 1))
        self.assertIsNone(await self.repository.get_by_ckan_resource_id(uuid4()))
        self.assertIsNone(await self.repository.get_by_feed_url("https://example.com/missing"))

    async def test_disabled_county_feed_remains_available_for_individual_lookups(self) -> None:
        feed = self.feed(enabled=False)
        await self.repository.add(feed)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            self.assertIsNotNone(await repository.get_by_id(feed.id))
            self.assertIsNotNone(await repository.get_by_feed_url(feed.feed_url))
            self.assertIsNotNone(await repository.get_by_ckan_resource_id(feed.ckan_resource_id))
            self.assertEqual(await repository.list_enabled(), [])

    async def test_enabled_list_is_ordered_and_all_reads_exclude_legacy_eu_feeds(self) -> None:
        first, disabled, last = self.feed(), self.feed(enabled=False), self.feed()
        for feed in [first, disabled, last]:
            await self.repository.add(feed)
        legacy = self.feed(scope="eu", county_id=None, label="Legacy EU feed")
        self.session.add(legacy)
        await self.session.commit()

        # The EU row is already present in the session's identity map.
        self.assertIsNone(await self.repository.get_by_id(legacy.id))
        self.assertIsNone(await self.repository.get_by_feed_url(legacy.feed_url))
        self.assertIsNone(await self.repository.get_by_ckan_resource_id(legacy.ckan_resource_id))
        self.assertEqual([feed.id for feed in await self.repository.list_enabled()], [first.id, last.id])
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            self.assertIsNone(await repository.get_by_id(legacy.id))
            self.assertIsNone(await repository.get_by_feed_url(legacy.feed_url))
            self.assertIsNone(await repository.get_by_ckan_resource_id(legacy.ckan_resource_id))
            self.assertEqual([feed.id for feed in await repository.list_enabled()], [first.id, last.id])

    async def test_unsupported_scopes_are_rejected_before_attaching_to_session(self) -> None:
        for scope in ["eu", "unknown", None]:
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "county"):
                await self.repository.add(self.feed(scope=scope, county_id=None))
        await self.repository.add(self.feed())
        await self.session.commit()
        async with self.sessions.session() as reader:
            self.assertEqual(await reader.scalar(select(func.count(SourceFeed.id))), 1)

    async def test_unique_errors_propagate_and_rollback_discards_earlier_writes(self) -> None:
        existing = self.feed()
        await self.repository.add(existing)
        await self.session.commit()
        for duplicate in [
            {"ckan_resource_id": existing.ckan_resource_id},
            {"feed_url": existing.feed_url},
        ]:
            with self.subTest(duplicate=duplicate):
                async with self.sessions.session() as writer:
                    repository = SqlAlchemySourceFeedRepository(writer)
                    pending = self.feed()
                    await repository.add(pending)
                    pending_id = pending.id
                    with self.assertRaises(IntegrityError):
                        await repository.add(self.feed(**duplicate))
                    await writer.rollback()
                    self.assertIsNone(await repository.get_by_id(pending_id))
                    self.assertIsNotNone(await repository.get_by_id(existing.id))
                async with self.sessions.session() as reader:
                    self.assertIsNone(await SqlAlchemySourceFeedRepository(reader).get_by_id(pending_id))

    async def test_loaded_sync_metadata_and_enabled_flag_are_updated_on_caller_commit(self) -> None:
        feed = self.feed()
        await self.repository.add(feed)
        await self.session.commit()
        now = datetime.now(timezone.utc)
        async with self.sessions.session() as writer:
            loaded = await SqlAlchemySourceFeedRepository(writer).get_by_ckan_resource_id(
                feed.ckan_resource_id
            )
            loaded.etag = '"revision-2"'
            loaded.last_checked_at = now
            loaded.last_success_at = now
            loaded.source_last_modified_at = now
            loaded.last_content_change_at = now
            loaded.enabled = False
            await writer.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            saved = await repository.get_by_id(feed.id)
            self.assertEqual(saved.etag, '"revision-2"')
            self.assertEqual(saved.last_checked_at, now)
            self.assertEqual(saved.last_success_at, now)
            self.assertEqual(saved.source_last_modified_at, now)
            self.assertEqual(saved.last_content_change_at, now)
            self.assertFalse(saved.enabled)
            self.assertEqual(await repository.list_enabled(), [])

    async def test_explicit_rollback_discards_feed_and_keeps_session_usable(self) -> None:
        feed = self.feed()
        await self.repository.add(feed)
        feed_id = feed.id
        await self.session.rollback()
        self.assertIsNone(await self.repository.get_by_id(feed_id))
        replacement = self.feed()
        await self.repository.add(replacement)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            self.assertIsNone(await repository.get_by_id(feed_id))
            self.assertIsNotNone(await repository.get_by_id(replacement.id))

    async def test_closing_context_without_commit_discards_feed(self) -> None:
        async with self.sessions.session() as writer:
            feed = self.feed()
            await SqlAlchemySourceFeedRepository(writer).add(feed)
            feed_id = feed.id
        async with self.sessions.session() as reader:
            self.assertIsNone(await SqlAlchemySourceFeedRepository(reader).get_by_id(feed_id))

    def changes(self, **overrides: object) -> dict[str, object]:
        values = {
            "county_id": self.county_id,
            "ckan_resource_id": uuid4(),
            "label": "Poslovi u Gradu Zagrebu",
            "feed_url": f"https://example.com/{uuid4()}.xml",
        }
        return values | overrides

    async def test_create_adds_enabled_county_feed_and_returns_dto(self) -> None:
        created = await self.repository.create(SourceFeedCreateDTO(**self.changes()))
        self.assertIsInstance(created, SourceFeedDTO)
        self.assertEqual((created.scope, created.enabled), ("county", True))
        self.assertEqual((await self.repository.get_by_id(created.id)).feed_url, created.feed_url)

    async def test_update_keeps_sync_state_and_resets_validators_only_on_request(self) -> None:
        now = datetime.now(timezone.utc)
        feed = self.feed(enabled=False, etag='"v1"', source_last_modified_at=now, last_checked_at=now)
        await self.repository.add(feed)
        for reset in (False, True):
            with self.subTest(reset=reset):
                updated = await self.repository.update(
                    feed.id, SourceFeedUpdateDTO(**self.changes(label=f"Label {reset}"), reset_http_validators=reset)
                )
                self.assertEqual(updated.label, f"Label {reset}")
                self.assertFalse(updated.enabled)
                self.assertEqual(feed.last_checked_at, now)
                self.assertEqual(feed.etag, None if reset else '"v1"')
                self.assertEqual(feed.source_last_modified_at, None if reset else now)

    async def test_update_of_missing_or_eu_feed_raises_not_found(self) -> None:
        legacy = self.feed(scope="eu", county_id=None)
        self.session.add(legacy)
        await self.session.flush()
        for feed_id in (legacy.id, legacy.id + 1):
            with self.subTest(feed_id=feed_id), self.assertRaises(NotFoundError):
                await self.repository.update(feed_id, SourceFeedUpdateDTO(**self.changes()))

    def occupation_feed(self, **overrides: object) -> SourceFeed:
        return self.feed(**({"scope": "occupation", "county_id": None, "label": "Zanimanje"} | overrides))

    async def test_occupation_feeds_are_found_and_listed_after_county_feeds(self) -> None:
        occupation, county, disabled = self.occupation_feed(), self.feed(), self.occupation_feed(enabled=False)
        for feed in [occupation, county, disabled]:
            await self.repository.add(feed)
        await self.session.commit()
        async with self.sessions.session() as reader:
            repository = SqlAlchemySourceFeedRepository(reader)
            self.assertEqual((await repository.get_by_id(occupation.id)).scope, "occupation")
            self.assertIsNotNone(await repository.get_by_feed_url(occupation.feed_url))
            self.assertIsNotNone(await repository.get_by_ckan_resource_id(disabled.ckan_resource_id))
            self.assertEqual([feed.id for feed in await repository.list_enabled()], [county.id, occupation.id])

    async def test_create_adds_occupation_feed_and_update_keeps_its_scope(self) -> None:
        created = await self.repository.create(SourceFeedCreateDTO(**self.changes(scope="occupation", county_id=None)))
        self.assertEqual((created.scope, created.county_id), ("occupation", None))
        updated = await self.repository.update(created.id, SourceFeedUpdateDTO(
            **self.changes(scope="occupation", county_id=None, label="Novi naziv"),
        ))
        self.assertEqual((updated.scope, updated.label), ("occupation", "Novi naziv"))
        with self.assertRaisesRegex(ValueError, "scope"):
            await self.repository.update(created.id, SourceFeedUpdateDTO(**self.changes()))

    def test_create_dto_requires_a_county_only_for_county_feeds(self) -> None:
        for overrides in ({"county_id": None}, {"scope": "occupation"}, {"scope": "eu", "county_id": None}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                SourceFeedCreateDTO(**self.changes(**overrides))
