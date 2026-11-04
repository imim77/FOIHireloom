import httpx

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.integrations.concrete.dzs import DzsClient
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.concrete.dzs_import import DzsImportService
from FOIHireloom.services.interfaces.dzs_import import DzsImportServiceInterface
from FOIHireloom.services.concrete.dzs_release_parser import DzsReleaseParser


class DzsImportServiceFactory:
    """Assemble the DZS import service from caller-owned resources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self, http: httpx.AsyncClient, uow_factory: UnitOfWorkFactory | None
    ) -> DzsImportServiceInterface:
        client = DzsClient(http, self._settings.DZS_TIMEOUT, self._settings.DZS_MAX_BYTES)
        catalog = CroatianCountyCatalog()
        return DzsImportService(client, DzsReleaseParser(catalog), uow_factory, catalog)
