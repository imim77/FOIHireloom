from collections.abc import Collection, Mapping, Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import Job
from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_sync import JobSnapshotDTO
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

    async def list_snapshots(self, provider: str, source_job_ids: Collection[str]) -> list[JobSnapshotDTO]:
        if not source_job_ids:
            return []
        statement = select(Job.id, Job.source_job_id, Job.content_hash).where(
            Job.provider == provider, Job.source_job_id.in_(source_job_ids)
        )
        result = await self._session.execute(statement)
        return [JobSnapshotDTO.model_validate(row) for row in result.all()]

    async def create_many(self, provider: str, jobs: Sequence[ParsedJobDTO], seen_at: datetime) -> dict[str, int]:
        entities = [
            Job(provider=provider, **self._content(job), first_seen_at=seen_at, last_seen_at=seen_at,
                content_changed_at=seen_at)
            for job in jobs
        ]
        self._session.add_all(entities)
        await self._session.flush()
        return {entity.source_job_id: entity.id for entity in entities}

    async def update_content(self, jobs: Mapping[int, ParsedJobDTO], seen_at: datetime) -> None:
        if jobs:
            await self._session.execute(update(Job), [
                {"id": job_id, **self._content(job), "last_seen_at": seen_at,
                 "content_changed_at": seen_at}
                for job_id, job in jobs.items()
            ])

    async def mark_seen(self, job_ids: Collection[int], seen_at: datetime) -> None:
        if job_ids:
            await self._session.execute(
                update(Job).where(Job.id.in_(job_ids)).values(last_seen_at=seen_at)
            )

    @staticmethod
    def _content(job: ParsedJobDTO) -> dict[str, object]:
        return job.model_dump() | {"quality_flags": list(job.quality_flags)}
