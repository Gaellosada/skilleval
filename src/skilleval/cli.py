"""`skilleval` on the command line. Specified in specs/cli.md."""

import argparse
import importlib.metadata
import sys
import time
import traceback
from enum import IntEnum

from skilleval.report import render
from skilleval.runner import UsageError, collect, run
from skilleval.testfile import LoadError


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
    `--version` and a bad flag return through argparse, as `OK` and `USAGE_ERROR`. An unexpected
    exception prints its traceback to stderr and returns `INTERNAL_ERROR`."""
    parser = argparse.ArgumentParser(
        prog="skilleval", description="Run the tests declared in *.eval.yml files."
    )
    parser.add_argument(
        "paths", nargs="*", help="files, directories or node ids; the current directory by default"
    )
    parser.add_argument("-k", metavar="WORD", help="keep only the cases whose node id contains WORD")
    parser.add_argument("-x", "--exitfirst", action="store_true", help="stop at the first failure or error")
    parser.add_argument(
        "-q", "--quiet", dest="verbosity", action="store_const", const=-1, default=0,
        help="print only the failures, the errors and the summary",
    )
    parser.add_argument(
        "-v", "--verbose", dest="verbosity", action="store_const", const=1, help="print one line per case"
    )
    parser.add_argument("--collect-only", action="store_true", help="list the node ids and run nothing")
    version = importlib.metadata.version("skilleval")
    parser.add_argument("--version", action="version", version=f"skilleval {version}")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return ExitCode.OK if e.code == 0 else ExitCode.USAGE_ERROR
    try:
        cases = collect(args.paths, args.k)
        if not cases:
            print("no cases collected")
            return ExitCode.NO_TESTS_COLLECTED
        if args.collect_only:
            print("\n".join(case.node_id for case in cases))
            return ExitCode.OK
        start = time.perf_counter()
        results = run(cases, args.exitfirst)
        print(render(results, args.verbosity, time.perf_counter() - start))
        failed = any(r.status in ("failed", "error") for r in results)
        return ExitCode.TESTS_FAILED if failed else ExitCode.OK
    except (LoadError, UsageError) as e:
        print(e, file=sys.stderr)
        return ExitCode.LOAD_ERROR if isinstance(e, LoadError) else ExitCode.USAGE_ERROR
    except Exception:
        traceback.print_exc()
        return ExitCode.INTERNAL_ERROR
