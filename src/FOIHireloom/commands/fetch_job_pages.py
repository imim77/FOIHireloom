"""Run `uv run --locked foihireloom-fetch-job-pages [--limit N]`.

    Sync jobs first. Prints a JSON summary; exits 1 if the run stopped early
    after repeated failed downloads, so a scheduler can alert on it.
"""

import argparse
import asyncio
import json
import sys

from FOIHireloom.config.settings import Settings
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services.dependency import DependencyService


class JobPageCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, limit: int | None = None) -> dict:
        async with DependencyService(self._settings).job_page_service() as service:
            return (await service.fetch_due(limit or self._settings.HZZ_PAGE_BATCH_SIZE)).model_dump()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch HZZ detail pages of listed jobs for their deadline and details.")
    parser.add_argument("--limit", type=int, help="Fetch at most this many pages (default: HZZ_PAGE_BATCH_SIZE).")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    try:
        result = asyncio.run(JobPageCommand(Settings()).run(args.limit))
    except (PersistenceError, OSError):
        print("Fetching job pages failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))
    if result["stopped_early"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
