from abc import ABC, abstractmethod
from datetime import datetime

from FOIHireloom.dto.hzz_feed import FeedResponseDTO


class HzzFeedClientInterface(ABC):
    """Download HZZ RSS feeds with conditional requests."""

    @abstractmethod
    async def fetch(
        self, url: str, etag: str | None = None, last_modified: datetime | None = None
    ) -> FeedResponseDTO:
        """Return the feed's bytes, or not_modified when the validators still match.

        The bytes are not decoded; the XML declaration names the encoding.
        Raise ValueError for a non-HTTP(S) URL and HzzFeedError when the feed
        cannot be downloaded within the configured limits.
        """
