from datetime import timedelta

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.domain.job_search import JobCursorCodec
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.feed_coverage import FeedCoverage
from FOIHireloom.services.concrete.job_comparison import JobComparator, JobConditionMatcher
from FOIHireloom.services.concrete.job_presentation import JobPresenter
from FOIHireloom.services.concrete.job_search import JobSearchService
from FOIHireloom.services.interfaces.job_search import JobSearchServiceInterface


class JobSearchServiceFactory:
    """Assemble the read-only job search service from a caller-owned Unit of Work factory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, uow_factory: UnitOfWorkFactory) -> JobSearchServiceInterface:
        coverage = FeedCoverage(timedelta(hours=self._settings.HZZ_STALE_AFTER_HOURS))
        return JobSearchService(
            uow_factory, CroatianCountyCatalog(), coverage, JobComparator(JobConditionMatcher()),
            JobPresenter(), JobCursorCodec(),
        )
