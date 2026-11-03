from abc import ABC, abstractmethod

from FOIHireloom.dto.county_indicators import (
    CountyComparisonDTO,
    CountyComparisonRequestDTO,
    UnemploymentHistoryDTO,
    UnemploymentHistoryRequestDTO,
)


class CountyIndicatorServiceInterface(ABC):
    """Compare counties by stored HZZ job ads and DZS registered unemployment; nothing here contacts HZZ or DZS."""

    @abstractmethod
    async def compare_counties(self, request: CountyComparisonRequestDTO) -> CountyComparisonDTO:
        """Compare 2 to 6 distinct counties, in the given order, as CountyComparisonDTO describes.

        The job filters choose the ads of filtered_jobs as market_stats()
        would; the indicators always use all active ads of each county.
        Without a succeeded DZS import the HZZ counts are still returned.
        Raise InvalidIndicatorRequestError for too few, too many, repeated
        or unknown counties, and InvalidJobSearchError for a query or place
        without words.
        """

    @abstractmethod
    async def unemployment_history(self, request: UnemploymentHistoryRequestDTO) -> UnemploymentHistoryDTO:
        """Return the monthly DZS unemployment rate of 1 to 6 distinct counties, as UnemploymentHistoryDTO describes.

        Raise InvalidIndicatorRequestError for too many, repeated or unknown counties.
        """
