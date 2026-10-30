from collections.abc import Callable

import httpx


async def read_limited(response: httpx.Response, max_bytes: int, too_large: Callable[[], Exception]) -> bytes:
    """Read a streamed body, raising too_large() once it exceeds max_bytes.

    Counted after decompression, so a small gzip body cannot expand unchecked.
    """
    chunks, size = [], 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise too_large()
        chunks.append(chunk)
    return b"".join(chunks)
