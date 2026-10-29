from collections.abc import Callable

import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.integrations.concrete.ckan import CkanClient
from FOIHireloom.services import (
    CroatianCountyCatalog,
    SourceFeedRegistrationPlanner,
    SourceFeedRegistrationService,
    SourceFeedRegistrationServiceInterface,
)


class SourceFeedRegistrationServiceFactory:
    """Assemble the registration service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self,
        http: httpx.AsyncClient,
        uow_factory: Callable[[], UnitOfWork] | None,
    ) -> SourceFeedRegistrationServiceInterface:
        """Pass uow_factory=None for a service that can only preview sources."""
        client = CkanClient(http, self._settings.CKAN_BASE_URL, self._settings.CKAN_TIMEOUT)
        planner = SourceFeedRegistrationPlanner(CroatianCountyCatalog())
        return SourceFeedRegistrationService(client, uow_factory, planner)
