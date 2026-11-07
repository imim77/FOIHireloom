import asyncio
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from FOIHireloom.dto.dzs import DzsFileResponseDTO
from FOIHireloom.exceptions import DzsFileError, DzsHttpError, DzsTooLargeError, DzsTransportError
from FOIHireloom.integrations.interfaces.dzs import DzsClientInterface

from .http import read_limited


class DzsClient(DzsClientInterface):
    """Download DZS files using a caller-owned async HTTP client, or read local copies.

    podaci.dzs.hr serves the files without Content-Length (chunked), so the
    size limit is enforced while reading.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 30.0,
        max_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("DZS timeout must be positive and finite.")
        if max_bytes <= 0:
            raise ValueError("DZS file size limit must be positive.")
        self._client = client
        self._timeout = timeout
        self._max_bytes = max_bytes

    async def fetch(self, url: str) -> DzsFileResponseDTO:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise ValueError("DZS file URL must be an HTTP(S) URL.")
        try:
            async with self._client.stream("GET", parsed, timeout=self._timeout, follow_redirects=True) as response:
                if not response.is_success:
                    raise DzsHttpError(response.status_code)
                content = await read_limited(response, self._max_bytes, self._too_large)
        except httpx.RequestError as error:
            raise DzsTransportError("Could not download the DZS file.") from error
        return DzsFileResponseDTO(
            content=content,
            last_modified=self._http_date(response.headers.get("last-modified")),
        )

    async def read(self, path: Path) -> DzsFileResponseDTO:
        try:
            content = await asyncio.to_thread(self._read_limited, path)
        except OSError as error:
            raise DzsFileError(f"Could not read {path}: {error.strerror or type(error).__name__}.") from error
        return DzsFileResponseDTO(content=content)

    def _read_limited(self, path: Path) -> bytes:
        with path.open("rb") as file:
            content = file.read(self._max_bytes + 1)
        if len(content) > self._max_bytes:
            raise self._too_large()
        return content

    def _too_large(self) -> DzsTooLargeError:
        return DzsTooLargeError(f"DZS file exceeds {self._max_bytes} bytes.")

    @staticmethod
    def _http_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
