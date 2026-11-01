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


class JobConditionsCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self) -> dict:
        async with DependencyService(self._settings).job_conditions_service() as service:
            return (await service.normalize_all()).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Normalise the working conditions of jobs with a fetched HZZ page.")
    parser.parse_args(argv)
    try:
        result = asyncio.run(JobConditionsCommand(Settings()).run())
    except (PersistenceError, OSError):
        print("Normalising job conditions failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
