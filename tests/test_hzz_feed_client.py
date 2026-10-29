import gzip
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from FOIHireloom.exceptions import HzzFeedHttpError, HzzFeedTooLargeError, HzzFeedTransportError
from FOIHireloom.integrations.concrete.hzz_feed import HzzFeedClient

FEED_URL = "http://burzarada.hzz.hr/rss/rsszup1.xml"
LAST_MODIFIED = "Thu, 29 Oct 2026 03:31:10 GMT"
ETAG = '"053c0f05567dd1:0"'


class HzzFeedClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.content = (Path(__file__).parent / "fixtures/hzz_feed_sample.xml").read_bytes()

    def hzz(self, requests: list[httpx.Request]):
        """Mimic the observed http->https 303 and ASP.NET cookie-check 302."""

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.scheme == "http":
                return httpx.Response(303, headers={"Location": str(request.url.copy_with(scheme="https"))})
            if "AspxAutoDetectCookieSupport" not in request.headers.get("cookie", ""):
                return httpx.Response(302, headers={
                    "Location": "/rss/rsszup1.xml?AspxAutoDetectCookieSupport=1",
                    "Set-Cookie": "AspxAutoDetectCookieSupport=1; path=/",
                })
            if request.headers.get("if-none-match") == ETAG:
                return httpx.Response(304, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})
            return httpx.Response(200, content=self.content, headers={
                "Content-Type": "text/xml", "ETag": ETAG, "Last-Modified": LAST_MODIFIED,
            })

        return respond

    async def test_follows_hzz_redirects_and_returns_undecoded_bytes_with_validators(self) -> None:
        requests: list[httpx.Request] = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(self.hzz(requests))) as http:
            response = await HzzFeedClient(http, timeout=3).fetch(FEED_URL)
            self.assertFalse(http.is_closed)
        self.assertFalse(response.not_modified)
        self.assertEqual(response.content, self.content)
        self.assertEqual(response.etag, ETAG)
        self.assertEqual(response.last_modified, datetime(2026, 10, 29, 3, 31, 10, tzinfo=timezone.utc))
        self.assertEqual([r.url.scheme for r in requests], ["http", "https", "https"])
        self.assertEqual(requests[0].extensions["timeout"]["read"], 3)

    async def test_matching_validators_survive_redirects_and_return_not_modified(self) -> None:
        requests: list[httpx.Request] = []
        saved = datetime(2026, 10, 29, 4, 31, 10, tzinfo=timezone(timedelta(hours=1)))
        async with httpx.AsyncClient(transport=httpx.MockTransport(self.hzz(requests))) as http:
            response = await HzzFeedClient(http).fetch(FEED_URL, etag=ETAG, last_modified=saved)
        self.assertTrue(response.not_modified)
        self.assertIsNone(response.content)
        self.assertEqual(response.etag, ETAG)
        self.assertEqual(requests[-1].headers["if-none-match"], ETAG)
        self.assertEqual(requests[-1].headers["if-modified-since"], LAST_MODIFIED)

    async def test_not_modified_without_validator_headers_keeps_the_request_values(self) -> None:
        saved = datetime(2026, 10, 29, 3, 31, 10, tzinfo=timezone.utc)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(304))) as http:
            response = await HzzFeedClient(http).fetch(FEED_URL, etag=ETAG, last_modified=saved)
        self.assertEqual((response.etag, response.last_modified), (ETAG, saved))

    async def test_missing_or_invalid_last_modified_is_none(self) -> None:
        for headers in ({}, {"Last-Modified": "not a date"}):
            with self.subTest(headers=headers):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=b"<rss/>", headers=headers)
                )) as http:
                    response = await HzzFeedClient(http).fetch(FEED_URL)
                self.assertIsNone(response.last_modified)
                self.assertIsNone(response.etag)

    async def test_http_errors_preserve_status(self) -> None:
        for status in (404, 429, 500, 503):
            with self.subTest(status=status):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(status, text="upstream error")
                )) as http:
                    with self.assertRaises(HzzFeedHttpError) as error:
                        await HzzFeedClient(http).fetch(FEED_URL)
                self.assertEqual(error.exception.status_code, status)

    async def test_transport_errors_and_redirect_loops_are_reported_without_retrying(self) -> None:
        def loop(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": str(request.url)})

        for exception in (httpx.ConnectError, httpx.ReadTimeout, None):
            calls: list[httpx.Request] = []

            def respond(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                if exception is None:
                    return loop(request)
                raise exception("dependency unavailable", request=request)

            with self.subTest(exception=exception):
                async with httpx.AsyncClient(transport=httpx.MockTransport(respond), max_redirects=3) as http:
                    with self.assertRaises(HzzFeedTransportError):
                        await HzzFeedClient(http).fetch(FEED_URL)
                    self.assertFalse(http.is_closed)
                self.assertEqual(len(calls), 1 if exception else 4)

    async def test_size_limit_applies_to_decompressed_content(self) -> None:
        body = gzip.compress(b"x" * 2048)
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=body, headers={"Content-Encoding": "gzip"})
        )) as http:
            with self.assertRaises(HzzFeedTooLargeError):
                await HzzFeedClient(http, max_bytes=1024).fetch(FEED_URL)
            response = await HzzFeedClient(http, max_bytes=2048).fetch(FEED_URL)
        self.assertEqual(len(response.content), 2048)

    async def test_invalid_url_and_configuration_are_rejected(self) -> None:
        async with httpx.AsyncClient() as http:
            for url in ("file:///etc/passwd", "burzarada.hzz.hr/rss/rsszup1.xml"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    await HzzFeedClient(http).fetch(url)
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    HzzFeedClient(http, timeout=timeout)
            with self.assertRaises(ValueError):
                HzzFeedClient(http, max_bytes=0)
