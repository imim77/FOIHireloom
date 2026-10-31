from collections.abc import Callable

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.services import JobConditionsNormalizer, JobConditionsService, JobConditionsServiceInterface


class JobConditionsServiceFactory:
    """Assemble the job conditions service from a caller-owned Unit of Work factory."""

    def create(self, uow_factory: Callable[[], UnitOfWork]) -> JobConditionsServiceInterface:
        return JobConditionsService(uow_factory, JobConditionsNormalizer())
