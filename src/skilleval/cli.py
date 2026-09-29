"""`skilleval` on the command line. Specified in specs/cli.md."""

import argparse
import importlib.metadata
import sys
import time
import traceback
from enum import IntEnum

from skilleval.report import Report
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
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-q", "--quiet", dest="verbosity", action="store_const", const=-1, default=0,
        help="print only the failures, the errors and the summary",
    )
    verbosity.add_argument(
        "-v", "--verbose", dest="verbosity", action="store_const", const=1, help="print one line per case"
    )
    kind = parser.add_mutually_exclusive_group()
    kind.add_argument(
        "--static-checks", dest="kind", action="store_const", const="static-check",
        help="keep only the static-check tests",
    )
    kind.add_argument(
        "--evaluations", dest="kind", action="store_const", const="evaluation", help="keep only the evaluation tests"
    )
    parser.add_argument("--collect-only", action="store_true", help="list the node ids and run nothing")
    version = importlib.metadata.version("skilleval")
    parser.add_argument("--version", action="version", version=f"skilleval {version}")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return ExitCode.OK if e.code == 0 else ExitCode.USAGE_ERROR
    try:
        cases = collect(args.paths, args.k, args.kind)
        if not cases:
            print("no cases collected")
            return ExitCode.NO_TESTS_COLLECTED
        if args.collect_only:
            print("\n".join(case.node_id for case in cases))
            return ExitCode.OK
        report = Report(args.verbosity)
        report.collected(len(cases))
        start = time.perf_counter()
        try:
            results = run(cases, args.exitfirst, started=report.started, finished=report.finished)
        except BaseException:
            print(flush=True)  # end the line a case left open, before the traceback
            raise
        report.ended(results, time.perf_counter() - start)
        failed = any(r.status in ("failed", "error") for r in results)
        return ExitCode.TESTS_FAILED if failed else ExitCode.OK
    except (LoadError, UsageError) as e:
        print(e, file=sys.stderr)
        return ExitCode.LOAD_ERROR if isinstance(e, LoadError) else ExitCode.USAGE_ERROR
    except Exception:
        traceback.print_exc()
        return ExitCode.INTERNAL_ERROR
