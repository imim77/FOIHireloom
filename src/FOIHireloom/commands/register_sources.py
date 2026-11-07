"""Run `uv run --locked foihireloom-register-sources [--dry-run]`.

    Apply Alembic migrations before writing. --dry-run needs only CKAN access.
"""

import argparse
import json

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import CkanError, SourceFeedRegistrationError
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface
from FOIHireloom.services.interfaces.lifecycle import DatabaseServiceOpener

from .command_line import CommandLine, CommandRun


class SourceFeedRegistrationCommand:
    """SourceFeedRegistrationCommand registers, or with dry_run only counts, the configured CKAN datasets' feeds."""

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


class SourceFeedRegistrationCommandLine(CommandLine[dict[str, int | bool]]):
    description = "Register Croatian county and occupation job feed sources from CKAN."
    failure = "Registration failed"
    reported_errors = (CkanError, SourceFeedRegistrationError, ValueError)

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--dry-run", action="store_true",
                            help="Validate and count sources without accessing the database.")

    def _start(self, args: argparse.Namespace) -> CommandRun[dict[str, int | bool]]:
        settings = Settings()
        command = SourceFeedRegistrationCommand(settings, DependencyService(settings).source_feed_registration_service)
        return command.run(args.dry_run)

    def _report(self, args: argparse.Namespace, result: dict[str, int | bool]) -> int:
        print(json.dumps(result, ensure_ascii=False))
        return 0


def main(argv: list[str] | None = None) -> None:
    SourceFeedRegistrationCommandLine().main(argv)


if __name__ == "__main__":
    main()
