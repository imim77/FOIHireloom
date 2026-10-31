from abc import ABC, abstractmethod

from FOIHireloom.dto.job_market import JobMarketFiltersDTO, JobMarketStatsDTO
from FOIHireloom.dto.job_search import (
    CategoryDTO,
    JobCardsPageDTO,
    JobDetailsDTO,
    JobSearchFiltersDTO,
    JobSearchPageDTO,
    RegionDTO,
)


class JobSearchServiceInterface(ABC):
    """Read stored HZZ job advertisements; nothing here contacts HZZ."""

    @abstractmethod
    async def search(self, filters: JobSearchFiltersDTO) -> JobSearchPageDTO:
        """Return one page of listed jobs, newest publication first.

        Query words match word prefixes with or without Croatian diacritics,
        and every word must match. Pass next_cursor back to get the next page.
        Raise NotFoundError for an unknown county and InvalidJobSearchError
        for a query without words or a malformed cursor.
        """

    @abstractmethod
    async def search_cards(self, filters: JobSearchFiltersDTO) -> JobCardsPageDTO:
        """Return the same page as search(), each job with the job page values a job card shows."""

    @abstractmethod
    async def market_stats(self, filters: JobMarketFiltersDTO) -> JobMarketStatsDTO:
        """Count the jobs search() would find for the same filters, by county, category, employer and page fields.

        Raise NotFoundError for an unknown county and InvalidJobSearchError
        for a query without words.
        """

    @abstractmethod
    async def get_job(self, job_id: int) -> JobDetailsDTO:
        """Return a job, listed or not, with its feed listings; raise NotFoundError if absent."""

    @abstractmethod
    async def list_regions(self) -> tuple[RegionDTO, ...]:
        """Return every county with the number of jobs a default search would find there."""

    @abstractmethod
    async def list_categories(self) -> tuple[CategoryDTO, ...]:
        """Return the categories of jobs a default search would find, most common first."""
