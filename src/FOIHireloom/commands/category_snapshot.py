"""Run `uv run --locked foihireloom-category-snapshot --out PATH`.

    Sync jobs first, and take the snapshot while no sync runs. Writes every
    listed job's category inputs and result, the feeds' fetch times and
    mappings and the coverage to PATH as JSON, and prints the coverage.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.category_snapshot import CategorySnapshotDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services.dependency import DependencyService


class CategorySnapshotCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self) -> CategorySnapshotDTO:
        async with DependencyService(self._settings).category_snapshot_service() as service:
            return await service.take()


def render(snapshot: CategorySnapshotDTO) -> str:
    """Indented JSON with one line per job row, which keeps the file small and diffable."""
    document = snapshot.model_dump(mode="json")
    rows = ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in document.pop("jobs"))
    head = json.dumps(document, ensure_ascii=False, indent=2).removesuffix("\n}")
    return f'{head},\n  "jobs": [\n{rows}\n  ]\n}}\n'


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Save a reference snapshot of the job category fill and its coverage.")
    parser.add_argument("--out", type=Path, required=True, help="Write the JSON snapshot to this file.")
    args = parser.parse_args(argv)
    try:
        snapshot = asyncio.run(CategorySnapshotCommand(Settings()).run())
    except (PersistenceError, OSError):
        print("Category snapshot failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        args.out.write_text(render(snapshot), encoding="utf-8")
    except OSError as error:
        print(f"Category snapshot failed: cannot write {args.out}: {error.strerror}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(snapshot.coverage.model_dump()))


if __name__ == "__main__":
    main()
