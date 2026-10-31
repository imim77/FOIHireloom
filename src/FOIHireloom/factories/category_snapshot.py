from collections.abc import Callable

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.services import CategorySnapshotService, CategorySnapshotServiceInterface


class CategorySnapshotServiceFactory:
    """Assemble the read-only category snapshot service from a caller-owned Unit of Work factory."""

    def create(self, uow_factory: Callable[[], UnitOfWork]) -> CategorySnapshotServiceInterface:
        return CategorySnapshotService(uow_factory)
