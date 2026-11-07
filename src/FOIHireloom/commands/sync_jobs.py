"""Run `uv run --locked foihireloom-sync-jobs [--feed-id ID]`.

    Register sources first. Prints a JSON summary; exits 1 if any feed
    failed or was rejected, so a scheduler can alert on it.
"""

import argparse
import json

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import NotFoundError
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .command_line import CommandLine, CommandRun


class JobSyncCommand:
    """JobSyncCommand syncs one feed or every enabled feed through an injected service opener."""

    def __init__(self, service: ServiceOpener[JobSyncServiceInterface]) -> None:
        self._open_service = service

    async def run(self, feed_id: int | None = None) -> dict:
        async with self._open_service() as service:
            if feed_id is not None:
                return {"feeds": [(await service.sync_feed(feed_id)).model_dump()]}
            return (await service.sync_all()).model_dump()


class JobSyncCommandLine(CommandLine[dict]):
    description = "Import job advertisements from registered HZZ county feeds and link occupation feeds."
    failure = "Sync failed"
    reported_errors = (NotFoundError,)

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--feed-id", type=int, help="Sync only this source feed, even if it is disabled.")

    def _start(self, args: argparse.Namespace) -> CommandRun[dict]:
        return JobSyncCommand(DependencyService(Settings()).job_sync_service).run(args.feed_id)

    def _report(self, args: argparse.Namespace, result: dict) -> int:
        print(json.dumps(result, ensure_ascii=False, default=str))
        return int(any(feed["status"] in {"failed", "rejected"} for feed in result["feeds"]))


def main(argv: list[str] | None = None) -> None:
    JobSyncCommandLine().main(argv)


if __name__ == "__main__":
    main()
