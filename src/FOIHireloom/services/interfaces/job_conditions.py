from abc import ABC, abstractmethod

from FOIHireloom.dto.job_conditions import JobConditionsRunDTO


class JobConditionsServiceInterface(ABC):
    """Keep the normalised conditions of jobs in step with their fetched pages."""

    @abstractmethod
    async def normalize_all(self) -> JobConditionsRunDTO:
        """Normalise the raw conditions of every job with a fetched page and store the ones that changed.

        Runs in one transaction; a second run with the same normaliser
        updates nothing.
        """
