import gzip
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import httpx

from FOIHireloom.exceptions import DzsFileError, DzsHttpError, DzsTooLargeError, DzsTransportError
from FOIHireloom.integrations.concrete.dzs import DzsClient

WORKBOOK_URL = "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx"
ETAG = '"1dd66c334388839"'
LAST_MODIFIED = "Wed, 28 Oct 2026 10:00:47 GMT"


class DzsClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_downloads_the_whole_file_with_its_validators(self) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.scheme == "http":
                return httpx.Response(301, headers={"Location": str(request.url.copy_with(scheme="https"))})
            return httpx.Response(200, content=b"PK\x03\x04xlsx", headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            response = await DzsClient(http, timeout=3).fetch(WORKBOOK_URL.replace("https", "http"))
            self.assertFalse(http.is_closed)
        self.assertEqual(response.content, b"PK\x03\x04xlsx")
        self.assertEqual(response.last_modified, datetime(2026, 10, 28, 10, 0, 47, tzinfo=timezone.utc))
        self.assertEqual([r.url.scheme for r in requests], ["http", "https"])
        self.assertEqual(requests[0].extensions["timeout"]["read"], 3)
        self.assertNotIn("if-none-match", requests[-1].headers)
        self.assertNotIn("if-modified-since", requests[-1].headers)

    async def test_missing_or_invalid_validators_are_none(self) -> None:
        for headers in ({}, {"Last-Modified": "not a date"}):
            with self.subTest(headers=headers):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=b"x", headers=headers)
                )) as http:
                    response = await DzsClient(http).fetch(WORKBOOK_URL)
                self.assertIsNone(response.last_modified)

    async def test_http_and_transport_errors(self) -> None:
        for status in (304, 404, 500):
            with self.subTest(status=status):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status))) as http:
                    with self.assertRaises(DzsHttpError) as error:
                        await DzsClient(http).fetch(WORKBOOK_URL)
                self.assertEqual(error.exception.status_code, status)

        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as http:
            with self.assertRaises(DzsTransportError):
                await DzsClient(http).fetch(WORKBOOK_URL)

    async def test_size_limit_applies_to_decompressed_downloads_and_local_files(self) -> None:
        body = gzip.compress(b"x" * 2048)
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=body, headers={"Content-Encoding": "gzip"})
        )) as http:
            with self.assertRaises(DzsTooLargeError):
                await DzsClient(http, max_bytes=1024).fetch(WORKBOOK_URL)
            self.assertEqual(len((await DzsClient(http, max_bytes=2048).fetch(WORKBOOK_URL)).content), 2048)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "t1.xlsx"
                path.write_bytes(b"y" * 2048)
                with self.assertRaises(DzsTooLargeError):
                    await DzsClient(http, max_bytes=2047).read(path)
                local = await DzsClient(http, max_bytes=2048).read(path)
                self.assertEqual((local.content, local.last_modified), (b"y" * 2048, None))
                for unreadable in (Path(directory) / "missing.xlsx", Path(directory)):
                    with self.subTest(path=unreadable), self.assertRaises(DzsFileError):
                        await DzsClient(http).read(unreadable)

    async def test_invalid_url_and_configuration_are_rejected(self) -> None:
        async with httpx.AsyncClient() as http:
            for url in ("file:///etc/passwd", "podaci.dzs.hr/media/t1.xlsx"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    await DzsClient(http).fetch(url)
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    DzsClient(http, timeout=timeout)
            with self.assertRaises(ValueError):
                DzsClient(http, max_bytes=0)
