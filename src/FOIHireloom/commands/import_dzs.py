"""Run `uv run --locked foihireloom-import-dzs [--t1-file PATH] [--workbook-file PATH] [--dry-run]`.

    Downloads DZS_T1_URL and DZS_WORKBOOK_URL unless local files are given.
    Register sources first, so that the 21 counties exist. --dry-run only
    reads and validates the files and needs no database. Prints a JSON
    summary; exits 1 if the import failed or was rejected.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.dzs import DzsSourceDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services.dependency import DependencyService


class DzsImportCommand:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, t1_file: Path | None = None, workbook_file: Path | None = None, dry_run: bool = False) -> dict:
        t1 = self._source(t1_file, self._settings.DZS_T1_URL)
        workbook = self._source(workbook_file, self._settings.DZS_WORKBOOK_URL)
        async with DependencyService(self._settings).dzs_import_service(with_database=not dry_run) as service:
            if dry_run:
                return (await service.validate_release(t1, workbook)).model_dump(mode="json")
            return (await service.import_release(t1, workbook)).model_dump(mode="json")

    @staticmethod
    def _source(path: Path | None, url: str) -> DzsSourceDTO:
        return DzsSourceDTO(location=url) if path is None else DzsSourceDTO(location=str(path), local=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Import DZS county labour-market data from release table T1 and the county workbook."
    )
    parser.add_argument("--t1-file", type=Path, help="Read the T1 XLSX from this file instead of DZS_T1_URL.")
    parser.add_argument("--workbook-file", type=Path,
                        help="Read the county workbook XLSX from this file instead of DZS_WORKBOOK_URL.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and validate the files without accessing the database.")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(DzsImportCommand(Settings()).run(args.t1_file, args.workbook_file, args.dry_run))
    except (PersistenceError, OSError):
        print("DZS import failed: check DATABASE_URL and apply Alembic migrations.", file=sys.stderr)
        raise SystemExit(1) from None
    except ValueError as error:
        print(f"DZS import failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] in {"failed", "rejected"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
