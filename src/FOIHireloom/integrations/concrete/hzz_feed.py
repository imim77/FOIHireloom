import math
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

import httpx

from FOIHireloom.dto.hzz_feed import FeedResponseDTO
from FOIHireloom.exceptions import HzzFeedHttpError, HzzFeedTooLargeError, HzzFeedTransportError
from FOIHireloom.integrations.interfaces.hzz_feed import HzzFeedClientInterface


class HzzFeedClient(HzzFeedClientInterface):
    """Download HZZ feeds using a caller-owned async HTTP client.

    HZZ redirects http to https (303) and then through an ASP.NET cookie check
    (302). Reuse one httpx.AsyncClient for a whole sync run so the cookie is
    sent only once; the caller closes it.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 15.0,
        max_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("HZZ feed timeout must be positive and finite.")
        if max_bytes <= 0:
            raise ValueError("HZZ feed size limit must be positive.")
        self._client = client
        self._timeout = timeout
        self._max_bytes = max_bytes

    async def fetch(
        self, url: str, etag: str | None = None, last_modified: datetime | None = None
    ) -> FeedResponseDTO:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise ValueError("HZZ feed URL must be an HTTP(S) URL.")
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified is not None:
            headers["If-Modified-Since"] = format_datetime(last_modified.astimezone(timezone.utc), usegmt=True)
        try:
            async with self._client.stream(
                "GET", parsed, headers=headers, timeout=self._timeout, follow_redirects=True
            ) as response:
                if response.status_code == 304:
                    return FeedResponseDTO(
                        not_modified=True,
                        etag=response.headers.get("etag") or etag,
                        last_modified=self._http_date(response.headers.get("last-modified")) or last_modified,
                    )
                if not response.is_success:
                    raise HzzFeedHttpError(response.status_code)
                content = await self._read_limited(response)
        except httpx.RequestError as error:
            raise HzzFeedTransportError("Could not download the HZZ feed.") from error
        return FeedResponseDTO(
            not_modified=False,
            content=content,
            etag=response.headers.get("etag"),
            last_modified=self._http_date(response.headers.get("last-modified")),
        )

    async def _read_limited(self, response: httpx.Response) -> bytes:
        # Counted after decompression, so a small gzip body cannot expand unchecked.
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise HzzFeedTooLargeError(f"HZZ feed exceeds {self._max_bytes} bytes.")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _http_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
