"""Run `uv run --locked foihireloom-normalize-job-conditions`.

    Normalises the conditions of every job with a fetched page again and
    stores the ones that changed: once after migrating, and whenever the
    normaliser's vocabulary changes. Prints a JSON summary.
"""

import argparse
import json

from FOIHireloom.config.settings import Settings
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_conditions import JobConditionsServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .command_line import CommandLine, CommandRun


class JobConditionsCommand:
    """JobConditionsCommand normalises every fetched job's conditions through an injected service opener."""

    def __init__(self, service: ServiceOpener[JobConditionsServiceInterface]) -> None:
        self._open_service = service

    async def run(self) -> dict:
        async with self._open_service() as service:
            return (await service.normalize_all()).model_dump()


class JobConditionsCommandLine(CommandLine[dict]):
    description = "Normalise the working conditions of jobs with a fetched HZZ page."
    failure = "Normalising job conditions failed"

    def _start(self, args: argparse.Namespace) -> CommandRun[dict]:
        return JobConditionsCommand(DependencyService(Settings()).job_conditions_service).run()

    def _report(self, args: argparse.Namespace, result: dict) -> int:
        print(json.dumps(result, ensure_ascii=False))
        return 0


def main(argv: list[str] | None = None) -> None:
    JobConditionsCommandLine().main(argv)


if __name__ == "__main__":
    main()
