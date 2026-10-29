# FOIHireloom

ChatGPT MCP application for job discovery, built with Python and FastMCP.

## Database configuration

Install the project dependencies with Python 3.14 or later:

```sh
uv sync --locked
cp .env.example .env
```

Set `DATABASE_URL` in `.env` or in the environment to your PostgreSQL
connection string. The application uses SQLAlchemy's async engine with the
`asyncpg` driver:

```text
postgresql+asyncpg://user:password@localhost:5432/foihireloom
```

`DATABASE_POOL_SIZE` defaults to 5 and `DATABASE_MAX_OVERFLOW` defaults to 10.
The shared engine is defined in `FOIHireloom.db.database`. Importing the
module configures the engine without opening a connection or creating tables.
The `.env` file is read relative to the working directory, so run commands
from the project root when using it.

`FOIHireloom.db.session` exposes the shared `async_session` factory and an
`AsyncDBContextManager`, following the
[reference project's session structure](https://github.com/anmarkoulis/layered-architecture/blob/main/src/layered_architecture/db/session.py):

```python
from sqlalchemy import text

from FOIHireloom.db.session import AsyncDBContextManager


async def check_database() -> int:
    async with AsyncDBContextManager() as session:
        result = await session.scalar(text("SELECT 1"))
        return result
```

Each context manager creates its own session, using the same engine and
connection pool. Repositories participating in one transaction should receive
that same session. Exiting the context closes the session and rolls back any
uncommitted transaction; it does not commit automatically. Writes must be
committed explicitly or through a future Unit of Work. Use a separate session
for each concurrent task.

Call `await close_database()` from `FOIHireloom.db.database` during application
shutdown once the database layer is connected to the server lifecycle.
Schema creation and Alembic migrations will be added with the ORM models.

## Tests

```sh
uv run --locked python -m unittest discover -s tests -v
```

The session tests exercise real transactions against temporary SQLite
databases using the development-only `aiosqlite` driver. They also check the
PostgreSQL engine configuration, but do not require or connect to a running
PostgreSQL server.
