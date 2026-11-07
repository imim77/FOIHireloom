import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from FOIHireloom.commands.forecast_accuracy import ForecastAccuracyCommand, main
from FOIHireloom.dto.forecast_accuracy import ForecastAccuracyRequestDTO
from FOIHireloom.exceptions import ForecastUnavailableError, PersistenceError

from test_forecast_accuracy import COUNTY, SnapshotWork, service


class FixedService:
    def __init__(self, report=None, error=None):
        self.report, self.error = report, error
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.report


def run_main(evaluator, *argv):
    class Dependencies:
        def __init__(self, settings):
            pass

        @contextlib.asynccontextmanager
        async def forecast_accuracy_service(self):
            yield evaluator

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("FOIHireloom.commands.forecast_accuracy.DependencyService", Dependencies), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main(list(argv))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class ForecastAccuracyCommandTests(unittest.TestCase):
    def setUp(self):
        evaluator, _ = service(SnapshotWork())
        self.report = asyncio.run(evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,))))

    def test_full_report_and_default_county_selection(self):
        evaluator = FixedService(self.report)
        code, out, err = run_main(evaluator)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), self.report.model_dump(mode="json"))
        self.assertEqual(len(evaluator.requests[0].counties), 21)

    def test_writes_evidence_and_prints_summary_with_explicit_options(self):
        evaluator = FixedService(self.report)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accuracy.json"
            code, out, err = run_main(evaluator, "--county", COUNTY.code, "--county", "medimurska", "--horizon", "12",
                                      "--windows", "2", "--sex", "women", "--end-period", "2025-09", "--out", str(path))
            saved = json.loads(path.read_text())
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(saved["counties"][0]["windows"][0]["points"])
        self.assertEqual(json.loads(out)["metrics"]["observations"], 18)
        request = evaluator.requests[0]
        self.assertEqual((request.counties, request.horizon, request.windows, request.sex),
                         ((COUNTY.code, "medimurska"), 12, 2, "women"))
        self.assertEqual(request.end_period.isoformat(), "2025-09-01")

    def test_no_evaluable_data_exits_2_and_still_emits_diagnostics(self):
        evaluator, _ = service(SnapshotWork(provenance=None))
        report = asyncio.run(evaluator.evaluate(ForecastAccuracyRequestDTO(counties=(COUNTY.code,))))
        code, out, err = run_main(FixedService(report), "--county", COUNTY.code)
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(json.loads(out)["status"], "unavailable")
        self.assertIsNone(json.loads(out)["metrics"]["mae_pp"])

    def test_invalid_arguments_do_not_open_the_service(self):
        for args in (("--horizon", "13"), ("--windows", "0"), ("--end-period", "2026-13"),
                     ("--end-period", "2026-09-01")):
            evaluator = FixedService(self.report)
            with self.subTest(args=args):
                code, out, err = run_main(evaluator, *args)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err)
                self.assertEqual(evaluator.requests, [])

    def test_model_database_and_output_errors_never_write_a_report(self):
        for error, message in ((ForecastUnavailableError("Install the forecast extra."), "forecast extra"),
                               (PersistenceError("secret database URL"), "DATABASE_URL")):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "accuracy.json"
                code, out, err = run_main(FixedService(error=error), "--out", str(path))
                self.assertFalse(path.exists())
            self.assertEqual((code, out), (1, ""))
            self.assertIn(message, err)
            self.assertNotIn("secret database", err)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "report.json"
            code, out, err = run_main(FixedService(self.report), "--out", str(path))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot write", err)


class ForecastAccuracyCommandInjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_injected_service_is_closed_on_model_failure(self):
        events = []

        @contextlib.asynccontextmanager
        async def opener():
            events.append("open")
            try:
                yield FixedService(error=ForecastUnavailableError("model failed"))
            finally:
                events.append("closed")

        command = ForecastAccuracyCommand(opener)
        with self.assertRaises(ForecastUnavailableError):
            await command.run(ForecastAccuracyRequestDTO(counties=(COUNTY.code,)))
        self.assertEqual(events, ["open", "closed"])
