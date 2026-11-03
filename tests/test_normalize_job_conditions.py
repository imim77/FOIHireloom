import contextlib
import io
import unittest
from unittest.mock import patch

from FOIHireloom.commands.normalize_job_conditions import main
from FOIHireloom.dto.job_conditions import JobConditionsRunDTO
from FOIHireloom.exceptions import PersistenceError


class FixedService:
    def __init__(self, result: JobConditionsRunDTO | None = None, error: Exception | None = None) -> None:
        self.result, self.error = result, error

    async def normalize_all(self) -> JobConditionsRunDTO:
        if self.error is not None:
            raise self.error
        return self.result


def run_main(service: FixedService) -> tuple[int, str, str]:
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def job_conditions_service(self):
            yield service

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("FOIHireloom.commands.normalize_job_conditions.DependencyService", FakeDependencyService), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main([])
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class NormalizeJobConditionsCommandErrorTests(unittest.TestCase):
    def test_database_error_exits_1(self) -> None:
        code, out, err = run_main(FixedService(error=PersistenceError("db down")))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)
