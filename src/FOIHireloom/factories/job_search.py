from collections.abc import Callable

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.services import CroatianCountyCatalog, JobSearchService, JobSearchServiceInterface


class JobSearchServiceFactory:
    """Assemble the read-only job search service from a caller-owned Unit of Work factory."""

    def create(self, uow_factory: Callable[[], UnitOfWork]) -> JobSearchServiceInterface:
        return JobSearchService(uow_factory, CroatianCountyCatalog())
