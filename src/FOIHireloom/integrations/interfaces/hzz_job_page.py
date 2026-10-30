from abc import ABC, abstractmethod


class HzzJobPageClientInterface(ABC):
    """Download the public HZZ detail page of one job advertisement."""

    @abstractmethod
    async def fetch(self, url: str) -> bytes:
        """Return the page's undecoded bytes.

        Raise ValueError for a URL that is not an HZZ job page,
        HzzJobPageUnavailableError when HZZ answers with its error page, and
        HzzJobPageError when the page cannot be downloaded within the limits.
        """
