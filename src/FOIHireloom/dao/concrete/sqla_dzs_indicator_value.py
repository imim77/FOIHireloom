from collections.abc import Collection, Sequence
from datetime import date, datetime

from sqlalchemy import Select, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.dao.interfaces.dzs_indicator_value import DzsIndicatorValueRepository
from FOIHireloom.db.models import County, DzsIndicatorValue
from FOIHireloom.dto.dzs import (
    DzsIndicator,
    DzsSex,
    DzsStoredValueDTO,
    DzsValueChangeDTO,
    DzsValueDTO,
    DzsValueSnapshotDTO,
)

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

    async def list_values(
        self, county_ids: Collection[int], indicators: Collection[DzsIndicator], sex: DzsSex,
        periods: Collection[date],
    ) -> list[DzsStoredValueDTO]:
        if not (county_ids and indicators and periods):
            return []
        statement = self._stored().where(
            DzsIndicatorValue.county_id.in_(county_ids), DzsIndicatorValue.indicator.in_(indicators),
            DzsIndicatorValue.sex == sex, DzsIndicatorValue.period.in_(periods),
        )
        return [DzsStoredValueDTO.model_validate(row) for row in (await self._session.execute(statement)).all()]

    async def list_series(
        self, county_ids: Collection[int], indicator: DzsIndicator, sex: DzsSex, first: date, last: date,
    ) -> list[DzsStoredValueDTO]:
        if not county_ids:
            return []
        statement = self._stored().where(
            DzsIndicatorValue.county_id.in_(county_ids), DzsIndicatorValue.indicator == indicator,
            DzsIndicatorValue.sex == sex, DzsIndicatorValue.period.between(first, last),
        ).order_by(DzsIndicatorValue.period, DzsIndicatorValue.county_id)
        return [DzsStoredValueDTO.model_validate(row) for row in (await self._session.execute(statement)).all()]

    async def latest_common_periods(
        self, county_ids: Collection[int], indicators: Collection[DzsIndicator], sex: DzsSex,
    ) -> dict[DzsIndicator, date]:
        counties = set(county_ids)
        if not (counties and indicators):
            return {}
        # The months in which every county has a known value, per indicator.
        common = (
            select(DzsIndicatorValue.indicator, DzsIndicatorValue.period)
            .where(DzsIndicatorValue.county_id.in_(counties), DzsIndicatorValue.indicator.in_(indicators),
                   DzsIndicatorValue.sex == sex, DzsIndicatorValue.value.is_not(None))
            .group_by(DzsIndicatorValue.indicator, DzsIndicatorValue.period)
            .having(func.count(DzsIndicatorValue.county_id.distinct()) == len(counties))
            .subquery()
        )
        statement = select(common.c.indicator, func.max(common.c.period)).group_by(common.c.indicator)
        return dict((await self._session.execute(statement)).all())

    @staticmethod
    def _stored() -> Select:
        return select(
            DzsIndicatorValue.county_id, DzsIndicatorValue.indicator, DzsIndicatorValue.period, DzsIndicatorValue.sex,
            *(getattr(DzsIndicatorValue, field) for field in CONTENT_FIELDS),
        )
