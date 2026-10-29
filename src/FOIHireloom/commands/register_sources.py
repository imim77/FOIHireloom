"""Run `uv run --locked foihireloom-register-sources [--dry-run]`.

    Apply Alembic migrations before writing. --dry-run needs only CKAN access.
"""

import argparse
import asyncio
from dataclasses import asdict
import json
import sys

import httpx
from sqlalchemy.exc import SQLAlchemyError

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.database import PostgresDatabase
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.exceptions import CkanError, PersistenceError
from FOIHireloom.integrations.concrete.ckan import CkanClient
from FOIHireloom.services.source_feed_registration import (
    SourceFeedRegistrationError, SourceFeedRegistrationPlanner, SourceFeedRegistrationService,
)


class SourceFeedRegistrationCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, dry_run: bool = False) -> dict[str, int | bool]:
        async with httpx.AsyncClient() as http:
            client = CkanClient(http, self._settings.CKAN_BASE_URL, self._settings.CKAN_TIMEOUT)
            if dry_run:
                planner = SourceFeedRegistrationPlanner()
                plan = planner.build(await client.get_resources(self._settings.CKAN_DATASET_ID))
                return {
                    "dry_run": True, "counties": len(planner.catalog.definitions),
                    "feeds": len(plan.sources), "resources_skipped": plan.resources_skipped,
                }
            database = PostgresDatabase(self._settings)
            try:
                service = SourceFeedRegistrationService(
                    client, SqlAlchemyUnitOfWorkFactory(SessionManager(database.engine))
                )
                result = await service.register_sources(self._settings.CKAN_DATASET_ID)
                return asdict(result)
            finally:
                await database.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register Croatian CKAN job feed sources.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count sources without accessing the database.")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(SourceFeedRegistrationCommand(Settings()).run(args.dry_run))
    except (SQLAlchemyError, PersistenceError, OSError):
        print("Registration failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    except (CkanError, SourceFeedRegistrationError, ValueError) as error:
        print(f"Registration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
