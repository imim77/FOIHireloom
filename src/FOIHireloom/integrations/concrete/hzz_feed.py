from datetime import datetime, timezone
from email.utils import format_datetime

import httpx

from FOIHireloom.dto.hzz_feed import FeedResponseDTO
from FOIHireloom.exceptions import HzzFeedHttpError, HzzFeedTooLargeError, HzzFeedTransportError
from FOIHireloom.integrations.interfaces.hzz_feed import HzzFeedClientInterface

from .http import HttpDownloadClient, http_date


class HzzFeedClient(HttpDownloadClient, HzzFeedClientInterface):
    """Download HZZ feeds using a caller-owned async HTTP client.

    HZZ redirects http to https (303) and then through an ASP.NET cookie check
    (302). Reuse one httpx.AsyncClient for a whole sync run so the cookie is
    sent only once; the caller closes it.
    """

    source = "HZZ feed"
    transport_error = HzzFeedTransportError
    too_large_error = HzzFeedTooLargeError

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 15.0,
        max_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        super().__init__(client, timeout, max_bytes)

    async def fetch(
        self, url: str, etag: str | None = None, last_modified: datetime | None = None
    ) -> FeedResponseDTO:
        parsed = self._http_url(url)
        async with self._stream(parsed, self._conditional_headers(etag, last_modified)) as response:
            if response.status_code == 304:
                return FeedResponseDTO(
                    not_modified=True,
                    etag=response.headers.get("etag") or etag,
                    last_modified=http_date(response.headers.get("last-modified")) or last_modified,
                )
            if not response.is_success:
                raise HzzFeedHttpError(response.status_code)
            content = await self._read_body(response)
        return FeedResponseDTO(
            not_modified=False,
            content=content,
            etag=response.headers.get("etag"),
            last_modified=http_date(response.headers.get("last-modified")),
        )

    @staticmethod
    def _conditional_headers(etag: str | None, last_modified: datetime | None) -> dict[str, str]:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified is not None:
            headers["If-Modified-Since"] = format_datetime(last_modified.astimezone(timezone.utc), usegmt=True)
        return headers
