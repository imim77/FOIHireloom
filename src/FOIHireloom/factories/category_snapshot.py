from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.services.concrete.category_snapshot import CategorySnapshotService
from FOIHireloom.services.interfaces.category_snapshot import CategorySnapshotServiceInterface


class CategorySnapshotServiceFactory:
    """Assemble the read-only category snapshot service from a caller-owned Unit of Work factory."""

    def create(self, uow_factory: UnitOfWorkFactory) -> CategorySnapshotServiceInterface:
        return CategorySnapshotService(uow_factory)
