"""Run `uv run --locked --extra forecast foihireloom-forecast-accuracy [--county CODE] [--out PATH]`.

    Evaluate DZS unemployment rates with rolling monthly origins. Omitting
    --county selects all 21 counties. Exit 2 means no window could be scored,
    exit 1 a database, model or output error. Forecast quality is reported,
    never forced to pass a threshold chosen after seeing the scores.
"""

import argparse
import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.forecast_accuracy import ForecastAccuracyReportDTO, ForecastAccuracyRequestDTO
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError
from FOIHireloom.services.concrete.croatian_counties import CroatianCountyCatalog
from FOIHireloom.services.dependency import DependencyService
from FOIHireloom.services.interfaces.forecast_accuracy import ForecastAccuracyServiceInterface
from FOIHireloom.services.interfaces.lifecycle import ServiceOpener

from .command_line import CommandLine, CommandRun

# Fields of the report printed when the full report goes to --out.
SUMMARY_FIELDS = {"status", "generated_at", "model", "end_period", "evaluated_windows", "skipped_windows", "metrics"}


class ForecastAccuracyCommand:
    """ForecastAccuracyCommand evaluates through an injected service opener and retains its cleanup on failure."""

    def __init__(self, service: ServiceOpener[ForecastAccuracyServiceInterface]) -> None:
        self._open_service = service

    async def run(self, request: ForecastAccuracyRequestDTO) -> ForecastAccuracyReportDTO:
        async with self._open_service() as service:
            return await service.evaluate(request)


def month(value: str) -> date:
    try:
        if len(value) != 7:
            raise ValueError
        return date.fromisoformat(value + "-01")
    except ValueError:
        raise argparse.ArgumentTypeError("Use a month as YYYY-MM, e.g. 2026-09.") from None


class ForecastAccuracyCommandLine(CommandLine[ForecastAccuracyReportDTO]):
    description = "Backtest DZS county unemployment-rate forecasts against known months."
    failure = "Forecast accuracy failed"
    database_advice = "check DATABASE_URL, PostgreSQL and Alembic migrations."
    reported_errors = (InvalidIndicatorRequestError, ForecastUnavailableError)

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--county", action="append",
                            help="County code or name; repeat for several. Default: all counties.")
        parser.add_argument("--horizon", type=int, default=6, help="Months per forecast, 1 to 12 (default 6).")
        parser.add_argument("--windows", type=int, default=3, help="Consecutive monthly origins, 1 to 12 (default 3).")
        parser.add_argument("--sex", choices=("total", "women", "men"), default="total")
        parser.add_argument("--end-period", type=month,
                            help="Last test month as YYYY-MM; default: latest common DZS month.")
        parser.add_argument("--out", type=Path, help="Save the full JSON report here and print a compact summary.")

    def _check(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
        try:
            args.request = ForecastAccuracyRequestDTO(
                counties=tuple(args.county or [county.code for county in CroatianCountyCatalog.definitions]),
                horizon=args.horizon, windows=args.windows, sex=args.sex, end_period=args.end_period,
            )
        except ValidationError as error:
            parser.error(str(error))

    def _start(self, args: argparse.Namespace) -> CommandRun[ForecastAccuracyReportDTO]:
        return ForecastAccuracyCommand(DependencyService(Settings()).forecast_accuracy_service).run(args.request)

    def _report(self, args: argparse.Namespace, result: ForecastAccuracyReportDTO) -> int:
        if args.out is None:
            print(result.model_dump_json(indent=2))
        else:
            self._save(args.out, result)
            print(json.dumps(result.model_dump(mode="json", include=SUMMARY_FIELDS), ensure_ascii=False, indent=2))
        return 2 if result.status == "unavailable" else 0

    def _save(self, path: Path, report: ForecastAccuracyReportDTO) -> None:
        try:
            path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            self._fail(f"cannot write {path}: {error.strerror}")


def main(argv: list[str] | None = None) -> None:
    ForecastAccuracyCommandLine().main(argv)


if __name__ == "__main__":
    main()
