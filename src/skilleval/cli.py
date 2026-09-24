"""`skilleval` on the command line. Specified in specs/cli.md."""

from enum import IntEnum


class ExitCode(IntEnum):
    """pytest's exit codes."""

    OK = 0
    TESTS_FAILED = 1
    LOAD_ERROR = 2
    INTERNAL_ERROR = 3
    USAGE_ERROR = 4
    NO_TESTS_COLLECTED = 5


def main(argv: list[str] | None = None) -> ExitCode:
    """Parse `argv` (`sys.argv[1:]` when None), collect, run, print, and return an `ExitCode`.
    An unexpected exception prints its traceback to stderr and returns `INTERNAL_ERROR`."""
    raise NotImplementedError
