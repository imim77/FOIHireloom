from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import Job
from FOIHireloom.dao.interfaces.job import JobRepository


class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: int) -> Job | None:
        return await self._session.get(Job, job_id)

    async def get_by_source_job_id(self, provider: str, source_job_id: str) -> Job | None:
        statement = select(Job).where(
            Job.provider == provider,
            Job.source_job_id == source_job_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_canonical_url(self, provider: str, canonical_url: str) -> Job | None:
        statement = select(Job).where(
            Job.provider == provider,
            Job.canonical_url == canonical_url,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, job: Job) -> None:
        self._session.add(job)
        await self._session.flush()
