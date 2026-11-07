"""Run `uv run --locked foihireloom-fetch-job-pages [--limit N]`.

    Sync jobs first. Prints a JSON summary; exits 1 if the run stopped early
    after repeated failed downloads, so a scheduler can alert on it.
"""

import argparse
import json

from FOIHireloom.config.settings import Settings
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_page import JobPageServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .command_line import CommandLine, CommandRun


class JobPageCommand:
    """JobPageCommand fetches due job pages, batch_size of them unless a run sets a limit."""

    def __init__(self, service: ServiceOpener[JobPageServiceInterface], batch_size: int) -> None:
        self._open_service = service
        self._batch_size = batch_size

    async def run(self, limit: int | None = None) -> dict:
        async with self._open_service() as service:
            return (await service.fetch_due(self._batch_size if limit is None else limit)).model_dump()


class JobPageCommandLine(CommandLine[dict]):
    description = "Fetch HZZ detail pages of listed jobs for their deadline and details."
    failure = "Fetching job pages failed"

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--limit", type=int, help="Fetch at most this many pages (default: HZZ_PAGE_BATCH_SIZE).")

    def _check(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")

    def _start(self, args: argparse.Namespace) -> CommandRun[dict]:
        settings = Settings()
        command = JobPageCommand(DependencyService(settings).job_page_service, settings.HZZ_PAGE_BATCH_SIZE)
        return command.run(args.limit)

    def _report(self, args: argparse.Namespace, result: dict) -> int:
        print(json.dumps(result, ensure_ascii=False))
        return int(result["stopped_early"])


def main(argv: list[str] | None = None) -> None:
    JobPageCommandLine().main(argv)


if __name__ == "__main__":
    main()
