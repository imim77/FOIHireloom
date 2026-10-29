from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import County
from FOIHireloom.dto.county import CountyDefinitionDTO, CountyDTO
from FOIHireloom.dao.interfaces.county import CountyRepository


class SqlAlchemyCountyRepository(CountyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> County | None:
        result = await self._session.execute(select(County).where(County.code == code))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> County | None:
        result = await self._session.execute(select(County).where(County.name == name))
        return result.scalar_one_or_none()

    async def add(self, county: County) -> None:
        self._session.add(county)
        await self._session.flush()

    async def create(self, county: CountyDefinitionDTO) -> CountyDTO:
        entity = County(code=county.code, name=county.name)
        await self.add(entity)
        return CountyDTO.model_validate(entity)
