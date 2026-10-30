from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from FOIHireloom.db.models import County, Job, JobFeedMembership, SourceFeed
from FOIHireloom.dto.county import CountyDefinitionDTO, CountyDTO
from FOIHireloom.dto.job_search import RegionDTO
from FOIHireloom.dao.concrete.sqla_job import open_condition
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

    async def list_regions(self, open_on: date) -> list[RegionDTO]:
        # A job listed in two feeds of the same county is counted once.
        open_jobs = (
            select(func.count(func.distinct(JobFeedMembership.job_id)))
            .select_from(JobFeedMembership)
            .join(SourceFeed)
            .join(Job, Job.id == JobFeedMembership.job_id)
            .where(
                SourceFeed.county_id == County.id,
                JobFeedMembership.presence_status == "present",
                open_condition(open_on),
            )
            .scalar_subquery()
        )
        statement = select(County.code, County.name, open_jobs.label("open_jobs")).order_by(County.name)
        result = await self._session.execute(statement)
        return [RegionDTO.model_validate(row) for row in result.all()]

    async def add(self, county: County) -> None:
        self._session.add(county)
        await self._session.flush()

    async def create(self, county: CountyDefinitionDTO) -> CountyDTO:
        entity = County(code=county.code, name=county.name)
        await self.add(entity)
        return CountyDTO.model_validate(entity)
