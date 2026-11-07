import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import ClassVar

import httpx


def http_date(value: str | None) -> datetime | None:
    """Parse an HTTP date header, reading a date without a zone as UTC; None when absent or invalid."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class HttpSourceClient:
    """HttpSourceClient reads one external source through a caller-owned httpx.AsyncClient.

    Subclasses set source to the name their error messages use, e.g. "CKAN".
    The caller closes the injected client, normally with an async context.
    """

    source: ClassVar[str]

    def __init__(self, client: httpx.AsyncClient, timeout: float) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(f"{self.source} timeout must be positive and finite.")
        self._client = client
        self._timeout = timeout


class HttpDownloadClient(HttpSourceClient):
    """HttpDownloadClient streams files from a source and stops at a size limit.

    Subclasses set the source's transport_error and too_large_error, which
    take a message. Redirects are followed, since the providers redirect
    http to https and through cookie checks.
    """

    transport_error: ClassVar[type[Exception]]
    too_large_error: ClassVar[type[Exception]]

    def __init__(self, client: httpx.AsyncClient, timeout: float, max_bytes: int) -> None:
        super().__init__(client, timeout)
        if max_bytes <= 0:
            raise ValueError(f"{self.source} size limit must be positive.")
        self._max_bytes = max_bytes

    def _http_url(self, url: str) -> httpx.URL:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise ValueError(f"{self.source} URL must be an HTTP(S) URL.")
        return parsed

    @asynccontextmanager
    async def _stream(
        self, url: httpx.URL | str, headers: dict[str, str] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Open a GET response; transport errors, also while reading it, raise transport_error."""
        try:
            async with self._client.stream(
                "GET", url, headers=headers, timeout=self._timeout, follow_redirects=True
            ) as response:
                yield response
        except httpx.RequestError as error:
            raise self.transport_error(f"Could not download the {self.source}.") from error

    async def _read_body(self, response: httpx.Response) -> bytes:
        """Read a streamed body, raising too_large_error once it exceeds the limit.

        Counted after decompression, so a small gzip body cannot expand unchecked.
        """
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise self._too_large()
            chunks.append(chunk)
        return b"".join(chunks)

    def _too_large(self) -> Exception:
        return self.too_large_error(f"{self.source} exceeds {self._max_bytes} bytes.")
