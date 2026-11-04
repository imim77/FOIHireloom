from datetime import timedelta

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.services.concrete.county_indicator_calculation import CountyIndicatorCalculator
from FOIHireloom.services.concrete.county_indicators import CountyIndicatorService
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.feed_coverage import FeedCoverage
from FOIHireloom.services.interfaces.county_indicators import CountyIndicatorServiceInterface


class CountyIndicatorServiceFactory:
    """Assemble the read-only county indicator service from a caller-owned Unit of Work factory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, uow_factory: UnitOfWorkFactory) -> CountyIndicatorServiceInterface:
        coverage = FeedCoverage(timedelta(hours=self._settings.HZZ_STALE_AFTER_HOURS))
        return CountyIndicatorService(uow_factory, CroatianCountyCatalog(), coverage, CountyIndicatorCalculator())
