import math
import re

import httpx

from FOIHireloom.exceptions import (
    HzzJobPageHttpError,
    HzzJobPageTooLargeError,
    HzzJobPageTransportError,
    HzzJobPageUnavailableError,
)
from FOIHireloom.integrations.interfaces.hzz_job_page import HzzJobPageClientInterface

from .http import read_limited

JOB_PAGE_URL = re.compile(r"^https?://burzarada\.hzz\.hr/RadnoMjesto_Ispis\.aspx\?WebSifra=\d+$")
ERROR_PAGE_PATH = "/errorpage.aspx"


class HzzJobPageClient(HzzJobPageClientInterface):
    """Download HZZ job pages using a caller-owned async HTTP client.

    Pages go through the same redirects and ASP.NET cookie check as the feeds;
    reuse one httpx.AsyncClient for a whole run. Only job page URLs are
    fetched, so stored URLs cannot send requests elsewhere.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 15.0,
        max_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("HZZ job page timeout must be positive and finite.")
        if max_bytes <= 0:
            raise ValueError("HZZ job page size limit must be positive.")
        self._client = client
        self._timeout = timeout
        self._max_bytes = max_bytes

    async def fetch(self, url: str) -> bytes:
        if not JOB_PAGE_URL.match(url):
            raise ValueError("Only HZZ job page URLs can be fetched.")
        try:
            async with self._client.stream("GET", url, timeout=self._timeout, follow_redirects=True) as response:
                if response.url.path.lower() == ERROR_PAGE_PATH:
                    raise HzzJobPageUnavailableError("HZZ showed its error page instead of the job.")
                if not response.is_success:
                    raise HzzJobPageHttpError(response.status_code)
                return await read_limited(
                    response, self._max_bytes,
                    lambda: HzzJobPageTooLargeError(f"HZZ job page exceeds {self._max_bytes} bytes."),
                )
        except httpx.RequestError as error:
            raise HzzJobPageTransportError("Could not download the HZZ job page.") from error
