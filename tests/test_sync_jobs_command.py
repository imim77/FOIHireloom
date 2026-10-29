import contextlib
import io
import json
import unittest
from unittest.mock import patch

from FOIHireloom.commands.sync_jobs import main
from FOIHireloom.dto.job_sync import FeedSyncResultDTO, JobSyncResultDTO
from FOIHireloom.exceptions import NotFoundError


class FakeSyncService:
    def __init__(self, *statuses: str) -> None:
        self.feeds = tuple(FeedSyncResultDTO(feed_id=i, label=f"FEED {i}", status=s) for i, s in enumerate(statuses, 1))

    async def sync_all(self) -> JobSyncResultDTO:
        statuses = [feed.status for feed in self.feeds]
        return JobSyncResultDTO(feeds=self.feeds, succeeded=statuses.count("succeeded"),
                                not_modified=statuses.count("not_modified"), failed=statuses.count("failed"),
                                rejected=statuses.count("rejected"))

    async def sync_feed(self, feed_id: int) -> FeedSyncResultDTO:
        if feed_id > len(self.feeds):
            raise NotFoundError("source feed", str(feed_id))
        return self.feeds[feed_id - 1]


def dependencies(service: FakeSyncService):
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def job_sync_service(self):
            yield service

    return patch("FOIHireloom.commands.sync_jobs.DependencyService", FakeDependencyService)


class SyncJobsCommandTests(unittest.TestCase):
    def run_main(self, service: FakeSyncService, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with dependencies(service), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                main(list(argv))
            except SystemExit as error:
                code = error.code
        return code, out.getvalue(), err.getvalue()

    def test_successful_run_prints_json_summary_and_exits_zero(self) -> None:
        code, out, _ = self.run_main(FakeSyncService("succeeded", "not_modified"))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["not_modified"], 1)

    def test_failed_or_rejected_feed_exits_nonzero_after_printing_summary(self) -> None:
        for status in ("failed", "rejected"):
            with self.subTest(status=status):
                code, out, _ = self.run_main(FakeSyncService("succeeded", status))
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out)["feeds"][1]["status"], status)

    def test_single_feed_and_unknown_feed(self) -> None:
        code, out, _ = self.run_main(FakeSyncService("succeeded"), "--feed-id", "1")
        self.assertEqual((code, json.loads(out)["feeds"][0]["feed_id"]), (0, 1))
        code, out, err = self.run_main(FakeSyncService("succeeded"), "--feed-id", "9")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("not found", err)
        self.assertNotIn("Traceback", err)
