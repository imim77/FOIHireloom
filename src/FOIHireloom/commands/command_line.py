import argparse
import asyncio
import sys
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any, ClassVar, NoReturn

from FOIHireloom.exceptions import PersistenceError

type CommandRun[Result] = Coroutine[Any, Any, Result]


class CommandLine[Result](ABC):
    """CommandLine runs one administrative command from its arguments to its exit status.

    Subclasses declare their arguments, start the run and report its result.
    Every command reports a failure the same way: one line on stderr that
    starts with failure, exit status 1 and no traceback. Database and OS
    errors print database_advice, since their own text may carry the
    DATABASE_URL; reported_errors print their message.
    """

    description: ClassVar[str]
    failure: ClassVar[str]
    database_advice: ClassVar[str] = "check DATABASE_URL and apply Alembic migrations."
    reported_errors: ClassVar[tuple[type[Exception], ...]] = ()

    def main(self, argv: list[str] | None = None) -> None:
        parser = argparse.ArgumentParser(description=self.description)
        self._add_arguments(parser)
        args = parser.parse_args(argv)
        self._check(parser, args)
        try:
            result = asyncio.run(self._start(args))
        except (PersistenceError, OSError):
            self._fail(self.database_advice)
        except self.reported_errors as error:
            self._fail(str(error))
        status = self._report(args, result)
        if status:
            raise SystemExit(status)

    def _add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Declare the command's options; a command without options keeps --help only."""

    def _check(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
        """Reject invalid arguments with parser.error() before any service opens."""

    @abstractmethod
    def _start(self, args: argparse.Namespace) -> CommandRun[Result]:
        """Assemble the command from the settings and return its run.

        Errors raised while assembling, such as invalid settings, are reported
        like errors of the run.
        """

    @abstractmethod
    def _report(self, args: argparse.Namespace, result: Result) -> int:
        """Print the result and return the exit status."""

    def _fail(self, reason: str) -> NoReturn:
        print(f"{self.failure}: {reason}", file=sys.stderr)
        raise SystemExit(1) from None
