"""Run `uv run --locked foihireloom-sync-jobs [--feed-id ID]`.

    Register sources first. Prints a JSON summary; exits 1 if any feed
    failed or was rejected, so a scheduler can alert on it.
"""

import argparse
import asyncio
import json
import sys

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import NotFoundError, PersistenceError
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener


class JobSyncCommand:
    def __init__(self, service: ServiceOpener[JobSyncServiceInterface]) -> None:
        self._open_service = service

    async def run(self, feed_id: int | None = None) -> dict:
        async with self._open_service() as service:
            if feed_id is not None:
                return {"feeds": [(await service.sync_feed(feed_id)).model_dump()]}
            return (await service.sync_all()).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import job advertisements from registered HZZ county feeds and link occupation feeds.")
    parser.add_argument("--feed-id", type=int, help="Sync only this source feed, even if it is disabled.")
    args = parser.parse_args(argv)
    try:
        command = JobSyncCommand(DependencyService(Settings()).job_sync_service)
        result = asyncio.run(command.run(args.feed_id))
    except (PersistenceError, OSError):
        print("Sync failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    except NotFoundError as error:
        print(f"Sync failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False, default=str))
    if any(feed["status"] in {"failed", "rejected"} for feed in result["feeds"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
