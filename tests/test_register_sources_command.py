import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from FOIHireloom.commands.register_sources import SourceFeedRegistrationCommand, main
from FOIHireloom.config.settings import Settings


def ckan_fixtures(request: httpx.Request) -> httpx.Response:
    """Serve the recorded county or occupation dataset requested by ID."""
    name = "ckan_occupation_package_show.json" if "zanimanju" in request.url.params["id"] else "ckan_package_show.json"
    return httpx.Response(200, json=json.loads((Path(__file__).parent / "fixtures" / name).read_text()))


class RegistrationCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_validates_live_shape_without_constructing_a_database(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(ckan_fixtures))
        settings = Settings(_env_file=None, DATABASE_URL="not-a-database-url")
        with patch("FOIHireloom.services.dependency.httpx.AsyncClient", return_value=http), patch(
            "FOIHireloom.services.dependency.PostgresDatabase", side_effect=AssertionError("Dry run must not access DB")
        ):
            result = await SourceFeedRegistrationCommand(settings).run(dry_run=True)
        self.assertEqual(
            result, {"dry_run": True, "counties": 21, "feeds": 39, "occupation_feeds": 18, "resources_skipped": 1}
        )
        self.assertTrue(http.is_closed)

    async def test_failed_dry_run_closes_http_client(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
        with patch("FOIHireloom.services.dependency.httpx.AsyncClient", return_value=http):
            with self.assertRaisesRegex(RuntimeError, "503"):
                await SourceFeedRegistrationCommand(Settings(_env_file=None)).run(dry_run=True)
        self.assertTrue(http.is_closed)


class RegistrationEntrypointTests(unittest.TestCase):
    def test_cli_reports_upstream_error_with_nonzero_exit_and_no_traceback(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
        output = io.StringIO()
        with patch("FOIHireloom.services.dependency.httpx.AsyncClient", return_value=http), contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                main(["--dry-run"])
        self.assertEqual(error.exception.code, 1)
        self.assertIn("HTTP 503", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_cli_prints_machine_readable_dry_run_result(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(ckan_fixtures))
        output = io.StringIO()
        with patch("FOIHireloom.services.dependency.httpx.AsyncClient", return_value=http), contextlib.redirect_stdout(output):
            main(["--dry-run"])
        self.assertEqual(json.loads(output.getvalue())["feeds"], 39)
