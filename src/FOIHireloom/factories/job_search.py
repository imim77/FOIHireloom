from collections.abc import Callable
from datetime import timedelta

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.services import (
    CroatianCountyCatalog,
    JobComparator,
    JobConditionMatcher,
    JobSearchService,
    JobSearchServiceInterface,
)


class JobSearchServiceFactory:
    """Assemble the read-only job search service from a caller-owned Unit of Work factory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, uow_factory: Callable[[], UnitOfWork]) -> JobSearchServiceInterface:
        stale_after = timedelta(hours=self._settings.HZZ_STALE_AFTER_HOURS)
        return JobSearchService(uow_factory, CroatianCountyCatalog(), stale_after, JobComparator(JobConditionMatcher()))
