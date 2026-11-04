import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.integrations.concrete.ckan import CkanClient
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.source_feed_registration import SourceFeedRegistrationPlanner, SourceFeedRegistrationService
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface


class SourceFeedRegistrationServiceFactory:
    """Assemble the registration service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self,
        http: httpx.AsyncClient,
        uow_factory: UnitOfWorkFactory | None,
    ) -> SourceFeedRegistrationServiceInterface:
        """Pass uow_factory=None for a service that can only preview sources."""
        client = CkanClient(http, self._settings.CKAN_BASE_URL, self._settings.CKAN_TIMEOUT)
        planner = SourceFeedRegistrationPlanner(CroatianCountyCatalog())
        return SourceFeedRegistrationService(client, uow_factory, planner)
