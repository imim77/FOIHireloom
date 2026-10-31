from collections.abc import Callable
from datetime import timedelta

import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.integrations.concrete.hzz_job_page import HzzJobPageClient
from FOIHireloom.services import HzzJobPageParser, JobConditionsNormalizer, JobPageService, JobPageServiceInterface


class JobPageServiceFactory:
    """Assemble the job page service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, http: httpx.AsyncClient, uow_factory: Callable[[], UnitOfWork]) -> JobPageServiceInterface:
        settings = self._settings
        client = HzzJobPageClient(http, settings.HZZ_PAGE_TIMEOUT, settings.HZZ_PAGE_MAX_BYTES)
        return JobPageService(
            client, HzzJobPageParser(), JobConditionsNormalizer(), uow_factory, settings.HZZ_PAGE_DELAY_SECONDS,
            timedelta(hours=settings.HZZ_PAGE_RETRY_HOURS), settings.HZZ_PAGE_MAX_CONSECUTIVE_FAILURES,
        )
