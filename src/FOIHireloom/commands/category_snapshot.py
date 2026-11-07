"""Run `uv run --locked foihireloom-category-snapshot --out PATH`.

    Sync jobs first, and take the snapshot while no sync runs. Writes every
    listed job's category inputs and result, the feeds' fetch times and
    mappings and the coverage to PATH as JSON, and prints the coverage.
"""

import argparse
import json
from pathlib import Path

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.category_snapshot import CategorySnapshotDTO
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.category_snapshot import CategorySnapshotServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .command_line import CommandLine, CommandRun


class CategorySnapshotCommand:
    """CategorySnapshotCommand takes the category snapshot through an injected service opener."""

    def __init__(self, service: ServiceOpener[CategorySnapshotServiceInterface]) -> None:
        self._open_service = service

    async def run(self) -> CategorySnapshotDTO:
        async with self._open_service() as service:
            return await service.take()


def render(snapshot: CategorySnapshotDTO) -> str:
    """Indented JSON with one line per job row, which keeps the file small and diffable."""
    document = snapshot.model_dump(mode="json")
    rows = ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in document.pop("jobs"))
    head = json.dumps(document, ensure_ascii=False, indent=2).removesuffix("\n}")
    return f'{head},\n  "jobs": [\n{rows}\n  ]\n}}\n'


class CategorySnapshotCommandLine(CommandLine[CategorySnapshotDTO]):
    description = "Save a reference snapshot of the job category fill and its coverage."
    failure = "Category snapshot failed"

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--out", type=Path, required=True, help="Write the JSON snapshot to this file.")

    def _start(self, args: argparse.Namespace) -> CommandRun[CategorySnapshotDTO]:
        return CategorySnapshotCommand(DependencyService(Settings()).category_snapshot_service).run()

    def _report(self, args: argparse.Namespace, result: CategorySnapshotDTO) -> int:
        try:
            args.out.write_text(render(result), encoding="utf-8")
        except OSError as error:
            self._fail(f"cannot write {args.out}: {error.strerror}")
        print(json.dumps(result.coverage.model_dump()))
        return 0


def main(argv: list[str] | None = None) -> None:
    CategorySnapshotCommandLine().main(argv)


if __name__ == "__main__":
    main()
