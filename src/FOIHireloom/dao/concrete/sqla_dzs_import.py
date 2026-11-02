from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from FOIHireloom.dao.interfaces.dzs_import import DzsImportRepository
from FOIHireloom.db.models import DzsImport, DzsImportFile
from FOIHireloom.dto.dzs import DzsImportOutcomeDTO
from FOIHireloom.exceptions import NotFoundError


class SqlAlchemyDzsImportRepository(DzsImportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, import_id: int) -> DzsImport | None:
        statement = select(DzsImport).where(DzsImport.id == import_id).options(selectinload(DzsImport.files))
        return await self._session.scalar(statement)

    async def start(self) -> int:
        run = DzsImport()
        self._session.add(run)
        await self._session.flush()
        return run.id

    async def finish(self, import_id: int, outcome: DzsImportOutcomeDTO, finished_at: datetime) -> None:
        run = await self._session.get(DzsImport, import_id)
        if run is None:
            raise NotFoundError("DZS import", str(import_id))
        for field, value in outcome.model_dump(exclude={"files"}).items():
            setattr(run, field, value)
        run.finished_at = finished_at
        self._session.add_all([
            DzsImportFile(
                import_id=import_id, role=file.role, location=file.location, sheets=list(file.sheets),
                sha256=file.sha256, size_bytes=file.size_bytes, etag=file.etag,
                source_last_modified_at=file.last_modified, fetched_at=file.fetched_at,
            )
            for file in outcome.files
        ])
        await self._session.flush()
