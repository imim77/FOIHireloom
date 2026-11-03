from collections.abc import Callable

import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.integrations.concrete.dzs import DzsClient
from FOIHireloom.services import CroatianCountyCatalog, DzsImportService, DzsImportServiceInterface, DzsReleaseParser


class DzsImportServiceFactory:
    """Assemble the DZS import service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self, http: httpx.AsyncClient, uow_factory: Callable[[], UnitOfWork] | None
    ) -> DzsImportServiceInterface:
        client = DzsClient(http, self._settings.DZS_TIMEOUT, self._settings.DZS_MAX_BYTES)
        catalog = CroatianCountyCatalog()
        return DzsImportService(client, DzsReleaseParser(catalog), uow_factory, catalog)
