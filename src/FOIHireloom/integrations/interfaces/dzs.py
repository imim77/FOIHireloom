from abc import ABC, abstractmethod
from pathlib import Path

from FOIHireloom.dto.dzs import DzsFileResponseDTO


class DzsClientInterface(ABC):
    """Obtain DZS release files, from their URL or from a local copy."""

    @abstractmethod
    async def fetch(self, url: str) -> DzsFileResponseDTO:
        """Download a file in full; DZS rewrites files at the same URL, so no validators are sent.

        Raise ValueError for a non-HTTP(S) URL and DzsError when the file
        cannot be downloaded within the configured limits.
        """

    @abstractmethod
    async def read(self, path: Path) -> DzsFileResponseDTO:
        """Read a local file under the same size limit; raise DzsError if it cannot be read."""
