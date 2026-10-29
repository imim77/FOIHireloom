from datetime import datetime

from .base import ModelConfigBaseModel


class FeedResponseDTO(ModelConfigBaseModel):
    """One conditional download of a feed.

    content is None exactly when not_modified is True. The validators are the
    ones to send next time; on 304 they fall back to the request's values.
    """

    not_modified: bool
    content: bytes | None = None
    etag: str | None = None
    last_modified: datetime | None = None
