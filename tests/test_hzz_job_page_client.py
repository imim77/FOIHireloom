import unittest
from pathlib import Path

import httpx

from FOIHireloom.exceptions import (
    HzzJobPageHttpError,
    HzzJobPageTooLargeError,
    HzzJobPageTransportError,
    HzzJobPageUnavailableError,
)
from FOIHireloom.integrations.concrete.hzz_job_page import HzzJobPageClient

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = "http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=167879154"


class HzzJobPageClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.page = (FIXTURES / "hzz_job_page_school.html").read_bytes()
        self.error_page = (FIXTURES / "hzz_job_page_error.html").read_bytes()
        self.requests: list[httpx.Request] = []

    def respond(self, request: httpx.Request) -> httpx.Response:
        """Mimic the observed http->https 303, the cookie-check 302 and the error page redirect."""
        self.requests.append(request)
        if request.url.scheme == "http":
            return httpx.Response(303, headers={"Location": str(request.url.copy_with(scheme="https"))})
        if request.url.path == "/ErrorPage.aspx":
            return httpx.Response(200, content=self.error_page, headers={"Content-Type": "text/html; charset=utf-8"})
        if "AspxAutoDetectCookieSupport" not in request.headers.get("cookie", ""):
            return httpx.Response(302, headers={
                "Location": f"{request.url.raw_path.decode()}&AspxAutoDetectCookieSupport=1",
                "Set-Cookie": "AspxAutoDetectCookieSupport=1; path=/",
            })
        if request.url.params["WebSifra"] == "1":
            return httpx.Response(302, headers={"Location": "/ErrorPage.aspx?errorCode=GenericError"})
        return httpx.Response(200, content=self.page, headers={"Content-Type": "text/html; charset=utf-8"})

    async def fetch(self, url: str = PAGE_URL, transport: httpx.MockTransport | None = None, **options) -> bytes:
        async with httpx.AsyncClient(transport=transport or httpx.MockTransport(self.respond)) as http:
            return await HzzJobPageClient(http, **options).fetch(url)

    async def test_follows_hzz_redirects_and_returns_page_bytes(self) -> None:
        self.assertEqual(await self.fetch(timeout=4), self.page)
        self.assertEqual([request.url.scheme for request in self.requests], ["http", "https", "https"])
        self.assertEqual(self.requests[0].extensions["timeout"]["read"], 4)

    async def test_error_page_means_the_job_page_is_unavailable(self) -> None:
        with self.assertRaises(HzzJobPageUnavailableError):
            await self.fetch("https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1")

    async def test_http_errors_timeouts_and_oversized_pages_raise_page_errors(self) -> None:
        with self.assertRaises(HzzJobPageHttpError) as raised:
            await self.fetch(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
        self.assertEqual(raised.exception.status_code, 503)

        def time_out(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        with self.assertRaises(HzzJobPageTransportError):
            await self.fetch(transport=httpx.MockTransport(time_out))
        with self.assertRaises(HzzJobPageTooLargeError):
            await self.fetch(max_bytes=100)

    async def test_only_hzz_job_page_urls_are_fetched(self) -> None:
        for url in ("https://example.com/RadnoMjesto_Ispis.aspx?WebSifra=1",
                    "https://burzarada.hzz.hr/rss/rsszup1.xml",
                    "file:///etc/passwd",
                    "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=1&x=2"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                await self.fetch(url)
        self.assertEqual(self.requests, [])

    def test_limits_must_be_positive(self) -> None:
        for options in ({"timeout": 0}, {"timeout": float("inf")}, {"max_bytes": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                HzzJobPageClient(httpx.AsyncClient(), **options)
