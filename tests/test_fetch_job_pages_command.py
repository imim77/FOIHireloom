import contextlib
import io
import json
import unittest
from unittest.mock import patch

from FOIHireloom.commands.fetch_job_pages import main
from FOIHireloom.dto.job_page import JobPageFetchResultDTO
from FOIHireloom.exceptions import PersistenceError


class FakeJobPageService:
    def __init__(self, stopped_early: bool = False, error: Exception | None = None) -> None:
        self.limits: list[int] = []
        self.stopped_early = stopped_early
        self.error = error

    async def fetch_due(self, limit: int) -> JobPageFetchResultDTO:
        self.limits.append(limit)
        if self.error is not None:
            raise self.error
        return JobPageFetchResultDTO(attempted=2, fetched=1, unavailable=1, failed=0, remaining=7,
                                     stopped_early=self.stopped_early)


def dependencies(service: FakeJobPageService):
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def job_page_service(self):
            yield service

    return patch("FOIHireloom.commands.fetch_job_pages.DependencyService", FakeDependencyService)


class FetchJobPagesCommandTests(unittest.TestCase):
    def run_main(self, service: FakeJobPageService, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with dependencies(service), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.dict("os.environ", {"HZZ_PAGE_BATCH_SIZE": "40"}):
            try:
                main(list(argv))
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_prints_summary_and_uses_the_configured_batch_size(self) -> None:
        service = FakeJobPageService()
        code, out, _ = self.run_main(service)
        self.assertEqual((code, service.limits), (0, [40]))
        self.assertEqual(json.loads(out)["remaining"], 7)
        self.run_main(service, "--limit", "3")
        self.assertEqual(service.limits[-1], 3)

    def test_exits_1_when_the_run_stopped_early_or_the_database_fails(self) -> None:
        self.assertEqual(self.run_main(FakeJobPageService(stopped_early=True))[0], 1)
        code, out, err = self.run_main(FakeJobPageService(error=PersistenceError("db down")))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)

    def test_limit_must_be_positive(self) -> None:
        code, _, err = self.run_main(FakeJobPageService(), "--limit", "0")
        self.assertEqual(code, 2)
        self.assertIn("--limit must be at least 1", err)
