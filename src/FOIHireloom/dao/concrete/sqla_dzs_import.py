from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from FOIHireloom.dao.interfaces.dzs_import import DzsImportRepository
from FOIHireloom.db.models import DzsImport, DzsImportFile
from FOIHireloom.dto.dzs import DzsImportFileRefDTO, DzsImportOutcomeDTO, DzsImportProvenanceDTO
from FOIHireloom.exceptions import NotFoundError

from .sqla_base import SqlAlchemyRepository


class SqlAlchemyDzsImportRepository(SqlAlchemyRepository, DzsImportRepository):
    async def get_by_id(self, import_id: int) -> DzsImport | None:
        statement = select(DzsImport).where(DzsImport.id == import_id).options(selectinload(DzsImport.files))
        return await self._session.scalar(statement)

    async def get_latest_succeeded(self) -> DzsImportProvenanceDTO | None:
        statement = (
            select(DzsImport)
            .where(DzsImport.status == "succeeded")
            .order_by(DzsImport.finished_at.desc(), DzsImport.id.desc())
            .limit(1)
            .options(selectinload(DzsImport.files))
        )
        run = await self._session.scalar(statement)
        if run is None:
            return None
        return DzsImportProvenanceDTO(
            import_id=run.id,
            finished_at=run.finished_at,
            files=tuple(
                DzsImportFileRefDTO(role=file.role, location=file.location, fetched_at=file.fetched_at,
                                    last_modified=file.source_last_modified_at)
                for file in run.files
            ),
        )

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
                sha256=file.sha256,
                source_last_modified_at=file.last_modified, fetched_at=file.fetched_at,
            )
            for file in outcome.files
        ])
        await self._session.flush()
