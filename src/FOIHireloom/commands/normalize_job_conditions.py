"""Run `uv run --locked foihireloom-normalize-job-conditions`.

    Normalises the conditions of every job with a fetched page again and
    stores the ones that changed: once after migrating, and whenever the
    normaliser's vocabulary changes. Prints a JSON summary.
"""

import argparse
import asyncio
import json
import sys

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_conditions import JobConditionsServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener


class JobConditionsCommand:
    def __init__(self, service: ServiceOpener[JobConditionsServiceInterface]) -> None:
        self._open_service = service

    async def run(self) -> dict:
        async with self._open_service() as service:
            return (await service.normalize_all()).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Normalise the working conditions of jobs with a fetched HZZ page.")
    parser.parse_args(argv)
    try:
        command = JobConditionsCommand(DependencyService(Settings()).job_conditions_service)
        result = asyncio.run(command.run())
    except (PersistenceError, OSError):
        print("Normalising job conditions failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
