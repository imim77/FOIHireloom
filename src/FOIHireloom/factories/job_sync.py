from collections.abc import Callable

import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.integrations.concrete.hzz_feed import HzzFeedClient
from FOIHireloom.services import FeedCategoryVerifier, HzzFeedParser, JobSyncService, JobSyncServiceInterface


class JobSyncServiceFactory:
    """Assemble the job sync service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, http: httpx.AsyncClient, uow_factory: Callable[[], UnitOfWork]) -> JobSyncServiceInterface:
        client = HzzFeedClient(http, self._settings.HZZ_FEED_TIMEOUT, self._settings.HZZ_FEED_MAX_BYTES)
        return JobSyncService(
            client, HzzFeedParser(), uow_factory, self._settings.HZZ_MIN_RETAINED_RATIO,
            FeedCategoryVerifier(self._settings.HZZ_OCCUPATION_MIN_EXAMPLES),
        )
