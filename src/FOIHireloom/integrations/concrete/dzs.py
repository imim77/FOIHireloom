import asyncio
from pathlib import Path

import httpx

from FOIHireloom.dto.dzs import DzsFileResponseDTO
from FOIHireloom.exceptions import DzsFileError, DzsHttpError, DzsTooLargeError, DzsTransportError
from FOIHireloom.integrations.interfaces.dzs import DzsClientInterface

from .http import HttpDownloadClient, http_date


class DzsClient(HttpDownloadClient, DzsClientInterface):
    """Download DZS files using a caller-owned async HTTP client, or read local copies.

    podaci.dzs.hr serves the files without Content-Length (chunked), so the
    size limit is enforced while reading.
    """

    source = "DZS file"
    transport_error = DzsTransportError
    too_large_error = DzsTooLargeError

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: float = 30.0,
        max_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        super().__init__(client, timeout, max_bytes)

    async def fetch(self, url: str) -> DzsFileResponseDTO:
        async with self._stream(self._http_url(url)) as response:
            if not response.is_success:
                raise DzsHttpError(response.status_code)
            content = await self._read_body(response)
        return DzsFileResponseDTO(content=content, last_modified=http_date(response.headers.get("last-modified")))

    async def read(self, path: Path) -> DzsFileResponseDTO:
        try:
            content = await asyncio.to_thread(self._read_local, path)
        except OSError as error:
            raise DzsFileError(f"Could not read {path}: {error.strerror or type(error).__name__}.") from error
        return DzsFileResponseDTO(content=content)

    def _read_local(self, path: Path) -> bytes:
        with path.open("rb") as file:
            content = file.read(self._max_bytes + 1)
        if len(content) > self._max_bytes:
            raise self._too_large()
        return content
