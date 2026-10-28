

from abc import ABC, abstractmethod

class JobRepository(ABC):

    @abstractmethod
    async def get_by_id(self, job_id: int) -> None:
        pass

    @abstractmethod
    async def add(self) -> None:
        pass
