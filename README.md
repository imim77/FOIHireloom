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
`PostgresDatabase` in `FOIHireloom.db.database` owns the engine and connection
pool. Constructing the object configures the engine without opening a
connection or creating tables. Importing modules does not create a database
object, engine, session factory, or settings instance.
The `.env` file is read relative to the working directory, so run commands
from the project root when using it.

`SessionManager` in `FOIHireloom.db.session` owns a session factory and creates
an `AsyncDBContextManager` for each operation. The module layout follows the
[reference project](https://github.com/anmarkoulis/layered-architecture/blob/main/src/layered_architecture/db/session.py),
with database resources encapsulated in objects and passed explicitly:

```python
from sqlalchemy import text

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import PostgresDatabase
from FOIHireloom.db.session import SessionManager


class DatabaseExample:
    def __init__(self, settings: Settings) -> None:
        self.database = PostgresDatabase(settings)
        self.sessions = SessionManager(self.database.engine)

    async def check_connection(self) -> int:
        async with self.sessions.session() as session:
            return await session.scalar(text("SELECT 1"))

    async def close(self) -> None:
        await self.database.close()
```

Each context manager creates its own session, using the same engine and
connection pool. Repositories participating in one transaction should receive
that same session. Exiting the context closes the session and rolls back any
uncommitted transaction; it does not commit automatically. Writes must be
committed explicitly or through a future Unit of Work. Use a separate session
for each concurrent task.

Create one `PostgresDatabase(Settings())` and its `SessionManager` per
application process, and pass the session manager to services that need it.
Call `await database.close()` during application shutdown once the database
layer is connected to the server lifecycle.
ORM models live in `FOIHireloom.db.models` and share `Base.metadata`.
Import that package to register all tables before running schema operations.
The application does not create or modify tables on startup.

## Schema migrations

Alembic configuration and revisions live in `src/FOIHireloom/db/alembic/`.
Use the same `DATABASE_URL` configuration as the application. From the project
root, apply migrations and check for differences from the ORM models:

```sh
uv run --locked alembic -c src/FOIHireloom/db/alembic/alembic.ini upgrade head
uv run --locked alembic -c src/FOIHireloom/db/alembic/alembic.ini check
```

The database must already exist. See the migration directory's `README` for
revision generation, offline SQL previews, and downgrade commands.

## Tests

```sh
uv run --locked python -m unittest discover -s tests -v
```

The session tests exercise real transactions against temporary SQLite
databases using the development-only `aiosqlite` driver. They also check the
PostgreSQL engine configuration, but do not require or connect to a running
PostgreSQL server.

ORM and migration integration tests use real PostgreSQL types and constraints. Set
`TEST_DATABASE_URL` in the process environment to a dedicated test database:

```sh
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foihireloom_test \
  uv run --locked python -m unittest discover -s tests -v
```

Each integration test creates a uniquely named schema and drops only that
schema afterwards. Model tests apply the migration history before testing
ORM operations. Migration tests also exercise downgrade/re-upgrade cycles and
detect differences from the ORM metadata. The test account needs permission
to create schemas. Without `TEST_DATABASE_URL`, PostgreSQL integration tests
are skipped; session and offline migration tests still run.
