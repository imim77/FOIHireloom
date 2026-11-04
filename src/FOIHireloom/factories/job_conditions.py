from FOIHireloom.db.uow.base import UnitOfWorkFactory
from FOIHireloom.services.concrete.job_conditions import JobConditionsNormalizer, JobConditionsService
from FOIHireloom.services.interfaces.job_conditions import JobConditionsServiceInterface


class JobConditionsServiceFactory:
    """Assemble the job conditions service from a caller-owned Unit of Work factory."""

    def create(self, uow_factory: UnitOfWorkFactory) -> JobConditionsServiceInterface:
        return JobConditionsService(uow_factory, JobConditionsNormalizer())
