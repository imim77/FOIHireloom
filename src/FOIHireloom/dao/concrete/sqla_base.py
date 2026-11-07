from pydantic import BaseModel
from sqlalchemy import Executable
from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyRepository:
    """SqlAlchemyRepository binds a repository to its Unit of Work's session.

    Every repository of one Unit of Work shares the session, so their changes
    commit or roll back together.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rows[Row: BaseModel](self, statement: Executable, row_type: type[Row]) -> list[Row]:
        """Return every result row validated as row_type."""
        result = await self._session.execute(statement)
        return [row_type.model_validate(row) for row in result.all()]
