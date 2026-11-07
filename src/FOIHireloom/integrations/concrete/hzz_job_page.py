import re

import httpx

from FOIHireloom.exceptions import (
    HzzJobPageHttpError,
    HzzJobPageTooLargeError,
    HzzJobPageTransportError,
    HzzJobPageUnavailableError,
)
from FOIHireloom.integrations.interfaces.hzz_job_page import HzzJobPageClientInterface

from .http import HttpDownloadClient

JOB_PAGE_URL = re.compile(r"^https?://burzarada\.hzz\.hr/RadnoMjesto_Ispis\.aspx\?WebSifra=\d+$")
ERROR_PAGE_PATH = "/errorpage.aspx"


class HzzJobPageClient(HttpDownloadClient, HzzJobPageClientInterface):
    """Download HZZ job pages using a caller-owned async HTTP client.

    Pages go through the same redirects and ASP.NET cookie check as the feeds;
    reuse one httpx.AsyncClient for a whole run. Only job page URLs are
    fetched, so stored URLs cannot send requests elsewhere.
    """

    source = "HZZ job page"
    transport_error = HzzJobPageTransportError
    too_large_error = HzzJobPageTooLargeError

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 15.0,
        max_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        super().__init__(client, timeout, max_bytes)

    async def fetch(self, url: str) -> bytes:
        if not JOB_PAGE_URL.match(url):
            raise ValueError("Only HZZ job page URLs can be fetched.")
        async with self._stream(url) as response:
            if response.url.path.lower() == ERROR_PAGE_PATH:
                raise HzzJobPageUnavailableError("HZZ showed its error page instead of the job.")
            if not response.is_success:
                raise HzzJobPageHttpError(response.status_code)
            return await self._read_body(response)
