"""Run `uv run --locked foihireloom-register-sources [--dry-run]`.

    Apply Alembic migrations before writing. --dry-run needs only CKAN access.
"""

import argparse
import asyncio
import json
import sys

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import CkanError, PersistenceError, SourceFeedRegistrationError
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface
from FOIHireloom.services.interfaces.lifecycle import DatabaseServiceOpener


class SourceFeedRegistrationCommand:
    def __init__(
        self, settings: Settings, service: DatabaseServiceOpener[SourceFeedRegistrationServiceInterface],
    ) -> None:
        self._settings = settings
        self._open_service = service

    async def run(self, dry_run: bool = False) -> dict[str, int | bool]:
        datasets = self._settings.CKAN_DATASET_ID, self._settings.CKAN_OCCUPATION_DATASET_ID
        async with self._open_service(with_database=not dry_run) as service:
            if dry_run:
                return {"dry_run": True, **(await service.preview_sources(*datasets)).model_dump()}
            return (await service.register_sources(*datasets)).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register Croatian county and occupation job feed sources from CKAN.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count sources without accessing the database.")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        command = SourceFeedRegistrationCommand(settings, DependencyService(settings).source_feed_registration_service)
        result = asyncio.run(command.run(args.dry_run))
    except (PersistenceError, OSError):
        print("Registration failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    except (CkanError, SourceFeedRegistrationError, ValueError) as error:
        print(f"Registration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
