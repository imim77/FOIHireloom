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


class SourceFeedRegistrationCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, dry_run: bool = False) -> dict[str, int | bool]:
        dependencies = DependencyService(self._settings)
        dataset_id = self._settings.CKAN_DATASET_ID
        async with dependencies.source_feed_registration_service(with_database=not dry_run) as service:
            if dry_run:
                return {"dry_run": True, **(await service.preview_sources(dataset_id)).model_dump()}
            return (await service.register_sources(dataset_id)).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register Croatian CKAN job feed sources.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count sources without accessing the database.")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(SourceFeedRegistrationCommand(Settings()).run(args.dry_run))
    except (PersistenceError, OSError):
        print("Registration failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    except (CkanError, SourceFeedRegistrationError, ValueError) as error:
        print(f"Registration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
