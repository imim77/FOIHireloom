from collections.abc import Callable
from datetime import timedelta

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.services import CountyIndicatorService, CountyIndicatorServiceInterface, CroatianCountyCatalog


class CountyIndicatorServiceFactory:
    """Assemble the read-only county indicator service from a caller-owned Unit of Work factory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, uow_factory: Callable[[], UnitOfWork]) -> CountyIndicatorServiceInterface:
        stale_after = timedelta(hours=self._settings.HZZ_STALE_AFTER_HOURS)
        return CountyIndicatorService(uow_factory, CroatianCountyCatalog(), stale_after)
