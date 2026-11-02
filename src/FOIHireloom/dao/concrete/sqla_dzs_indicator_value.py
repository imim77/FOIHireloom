from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.dao.interfaces.dzs_indicator_value import DzsIndicatorValueRepository
from FOIHireloom.db.models import County, DzsIndicatorValue
from FOIHireloom.dto.dzs import DzsValueChangeDTO, DzsValueDTO, DzsValueSnapshotDTO

CONTENT_FIELDS = ("value", "missing_reason", "is_provisional", "source")


class SqlAlchemyDzsIndicatorValueRepository(DzsIndicatorValueRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_snapshots(self) -> list[DzsValueSnapshotDTO]:
        statement = select(
            DzsIndicatorValue.id, County.iso_code.label("county_iso"), DzsIndicatorValue.indicator,
            DzsIndicatorValue.period, DzsIndicatorValue.sex, *(getattr(DzsIndicatorValue, f) for f in CONTENT_FIELDS),
        ).join(County)
        result = await self._session.execute(statement)
        return [DzsValueSnapshotDTO.model_validate(row) for row in result.all()]

    async def create_many(self, values: Sequence[DzsValueDTO], import_id: int, written_at: datetime) -> None:
        if not values:
            return
        county_ids = dict((await self._session.execute(select(County.iso_code, County.id))).all())
        unknown = sorted({str(value.county_iso) for value in values if value.county_iso not in county_ids})
        if unknown:
            raise ValueError(f"DZS values need stored counties; unknown ISO codes: {', '.join(unknown)}.")
        rows = [
            {
                "county_id": county_ids[value.county_iso], "indicator": value.indicator, "period": value.period,
                "sex": value.sex, **value.model_dump(include=set(CONTENT_FIELDS)), "import_id": import_id,
                "created_at": written_at, "updated_at": written_at,
            }
            for value in values
        ]
        await self._session.execute(insert(DzsIndicatorValue), rows)

    async def update_many(self, changes: Sequence[DzsValueChangeDTO], import_id: int, written_at: datetime) -> None:
        # Rows that keep revised_at have one column fewer, so each kind is sent as its own batch.
        for revised in (True, False):
            rows = [
                {
                    "id": change.id, **change.value.model_dump(include=set(CONTENT_FIELDS)), "import_id": import_id,
                    "updated_at": written_at, **({"revised_at": written_at} if revised else {}),
                }
                for change in changes if change.revised == revised
            ]
            if rows:
                await self._session.execute(update(DzsIndicatorValue), rows)
