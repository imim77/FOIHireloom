import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func

from model_test_case import ModelTestCase

from FOIHireloom.commands.category_snapshot import main
from FOIHireloom.dao.concrete.sqla_job import SqlAlchemyJobRepository
from FOIHireloom.dao.concrete.sqla_source_feed import SqlAlchemySourceFeedRepository
from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.category_snapshot import CategoryCoverageDTO, CategoryInputDTO, CategorySnapshotDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services import CategorySnapshotService

HEALTH, TRANSPORT, TEXTILES = "ZDRAVSTVO, SOCIJALNA SKRB, NJEGA", "STRUČNJACI U PROMETU", "TEKSTILCI I KOŽARI"


class FixedService:
    def __init__(self, snapshot: CategorySnapshotDTO | None = None, error: Exception | None = None) -> None:
        self.snapshot, self.error = snapshot, error

    async def take(self) -> CategorySnapshotDTO:
        if self.error is not None:
            raise self.error
        return self.snapshot


def run_main(service: FixedService, *argv: str) -> tuple[int, str, str]:
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def category_snapshot_service(self):
            yield service

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("FOIHireloom.commands.category_snapshot.DependencyService", FakeDependencyService), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main(list(argv))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class CategorySnapshotTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        county = County(code="grad-zagreb", name="Grad Zagreb")
        self.session.add(county)
        await self.session.flush()
        verified = {"mapping_verified_at": func.now(), "mapping_contradicting_examples": 0}
        feeds = {
            "county": SourceFeed(county_id=county.id, scope="county", label="GRAD ZAGREB"),
            "transport": SourceFeed(scope="occupation", label="A", mapped_category=TRANSPORT, mapping_status="confirmed",
                                    mapping_matching_examples=5, **verified),
            "transport2": SourceFeed(scope="occupation", label="B", mapped_category=TRANSPORT,
                                     mapping_status="confirmed", mapping_matching_examples=3, **verified),
            "textiles": SourceFeed(scope="occupation", label="C", mapped_category=TEXTILES, mapping_status="confirmed",
                                   mapping_matching_examples=4, **verified),
            "few": SourceFeed(scope="occupation", label="D", mapped_category=HEALTH, mapping_status="too_few_examples",
                              mapping_matching_examples=1, **verified),
            "eu": SourceFeed(scope="eu", label="EU"),
        }
        for feed in feeds.values():
            feed.ckan_resource_id, feed.feed_url = uuid4(), f"http://burzarada.hzz.hr/rss/{uuid4()}.xml"
            self.session.add(feed)
            await self.session.flush()
        self.feeds = {key: feed.id for key, feed in feeds.items()}
        # The unlisted job left its county feed, so neither it nor its category is in the snapshot.
        for key, category, source, feed, listings in (
            ("explicit", HEALTH, "description", None, {"county": "present", "few": "present"}),
            ("filled", TRANSPORT, "feed", "transport", {"county": "present", "transport2": "present",
                                                        "transport": "missing"}),
            ("unknown", None, None, None, {"county": "present", "few": "present"}),
            ("conflict", None, None, None, {"county": "present", "transport": "present", "textiles": "present"}),
            ("unlisted", TEXTILES, "feed", "textiles", {"county": "missing", "textiles": "present"}),
        ):
            job = Job(provider="hzz", source_job_id=key, canonical_url=f"https://example.com/{key}", content_hash=key,
                      category=category, category_source=source, category_feed_id=feed and self.feeds[feed])
            self.session.add(job)
            await self.session.flush()
            self.session.add_all([
                JobFeedMembership(job_id=job.id, feed_id=self.feeds[name], presence_status=status,
                                  missing_since_at=func.now() if status == "missing" else None)
                for name, status in listings.items()
            ])
        await self.session.commit()
        self.service = CategorySnapshotService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)))

    async def test_reads_listed_jobs_inputs_and_synced_feeds(self) -> None:
        jobs = await SqlAlchemyJobRepository(self.session).list_category_inputs()
        feeds = self.feeds
        self.assertEqual(jobs, [
            CategoryInputDTO(source_job_id="explicit", description_category=HEALTH, occupation_feed_ids=(feeds["few"],),
                             category=HEALTH, category_source="description", category_feed_id=None),
            CategoryInputDTO(source_job_id="filled", description_category=None,
                             occupation_feed_ids=(feeds["transport"], feeds["transport2"]), category=TRANSPORT,
                             category_source="feed", category_feed_id=feeds["transport"]),
            CategoryInputDTO(source_job_id="unknown", description_category=None, occupation_feed_ids=(feeds["few"],),
                             category=None, category_source=None, category_feed_id=None),
            CategoryInputDTO(source_job_id="conflict", description_category=None,
                             occupation_feed_ids=(feeds["transport"], feeds["textiles"]), category=None,
                             category_source=None, category_feed_id=None),
        ])
        synced = await SqlAlchemySourceFeedRepository(self.session).list_synced()
        self.assertEqual([feed.id for feed in synced], [feeds[key] for key in feeds if key != "eu"])

    async def test_snapshot_counts_coverage_and_refers_to_categories_by_index(self) -> None:
        snapshot = await self.service.take()
        self.assertEqual(snapshot.coverage.model_dump(),
                         {"listed": 4, "before": 1, "after": 2, "filled": 1, "unknown": 2, "conflicting": 1})
        self.assertEqual(snapshot.categories, (TRANSPORT, HEALTH))
        feeds = self.feeds
        self.assertEqual(snapshot.jobs, (
            ("explicit", 1, (feeds["few"],), 1, "description", None),
            ("filled", None, (feeds["transport"], feeds["transport2"]), 0, "feed", feeds["transport"]),
            ("unknown", None, (feeds["few"],), None, None, None),
            ("conflict", None, (feeds["transport"], feeds["textiles"]), None, None, None),
        ))
        few = next(feed for feed in snapshot.feeds if feed.id == feeds["few"])
        self.assertEqual((few.scope, few.mapped_category, few.mapping_status, few.mapping_matching_examples),
                         ("occupation", HEALTH, "too_few_examples", 1))
        self.assertIsNotNone(snapshot.generated_at.tzinfo)

    async def test_command_writes_the_snapshot_one_job_per_line_and_prints_coverage(self) -> None:
        snapshot = await self.service.take()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            # The command starts its own event loop.
            code, out, _ = await asyncio.to_thread(run_main, FixedService(snapshot), "--out", str(path))
            text = path.read_text(encoding="utf-8")
        self.assertEqual((code, json.loads(out)), (0, snapshot.coverage.model_dump()))
        self.assertEqual(CategorySnapshotDTO.model_validate_json(text), snapshot)
        transport, transport2 = self.feeds["transport"], self.feeds["transport2"]
        self.assertIn(f'\n    ["filled", null, [{transport}, {transport2}], 0, "feed", {transport}],\n', text)


class CategorySnapshotCommandErrorTests(unittest.TestCase):
    def test_database_error_exits_1_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            code, out, err = run_main(FixedService(error=PersistenceError("db down")), "--out", str(path))
            self.assertFalse(path.exists())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)

    def test_unwritable_out_exits_1(self) -> None:
        empty = CategorySnapshotDTO(
            generated_at=datetime.now(UTC), denominator="", feeds=(), categories=(), jobs=(),
            coverage=CategoryCoverageDTO(listed=0, before=0, after=0, filled=0, unknown=0, conflicting=0),
        )
        with tempfile.TemporaryDirectory() as directory:
            code, out, err = run_main(FixedService(empty), "--out", str(Path(directory) / "missing" / "s.json"))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot write", err)
