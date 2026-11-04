import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.integrations.concrete.hzz_feed import HzzFeedClient
from FOIHireloom.services.concrete.feed_category import FeedCategoryVerifier
from FOIHireloom.services.concrete.hzz_feed_parser import HzzFeedParser
from FOIHireloom.services.concrete.job_sync import JobSyncService
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface


class JobSyncServiceFactory:
    """Assemble the job sync service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, http: httpx.AsyncClient, uow_factory: UnitOfWorkFactory) -> JobSyncServiceInterface:
        client = HzzFeedClient(http, self._settings.HZZ_FEED_TIMEOUT, self._settings.HZZ_FEED_MAX_BYTES)
        return JobSyncService(
            client, HzzFeedParser(), uow_factory, self._settings.HZZ_MIN_RETAINED_RATIO,
            FeedCategoryVerifier(self._settings.HZZ_OCCUPATION_MIN_EXAMPLES),
        )
