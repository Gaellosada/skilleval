"""Collection and execution: node ids, discovery, `needs`. Specified in specs/cli.md and specs/README.md."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skilleval.static import CheckResult
from skilleval.testfile import Test, TestFile

SKIPPED_DIRS = frozenset({"node_modules", "venv", "site-packages"})
Status = Literal["passed", "failed", "skipped", "error"]


class UsageError(Exception):
    """A bad invocation: a path that does not exist, a node id that matches nothing, brackets
    on a case that has none. Exit code 4."""


@dataclass(frozen=True)
class Case:
    """One runnable unit. `prompt_path` is the file behind it, None for a text prompt and for
    an `include` that matched nothing (`test.prompt` tells them apart). `node_id` is
    `<file>::<id>` or `<file>::<id>[<prompt_path>]`, both paths posix and relative to the
    current directory."""

    node_id: str
    file: TestFile
    test: Test
    prompt_path: Path | None = None


@dataclass(frozen=True)
class CaseResult:
    """`status` is `passed`, `failed`, `skipped` or `error`; `reason` says why for the last two."""

    case: Case
    status: Status
    checks: tuple[CheckResult, ...] = ()
    reason: str | None = None


def collect(args: list[str], keyword: str | None = None) -> list[Case]:
    """Turn paths and node ids into cases, files in argument order, tests in `TestFile.tests`
    order, fan-out matches sorted, a case named twice collected once. No args means the
    current directory. `keyword` keeps the node ids containing it. Raises `LoadError` for a bad file and `UsageError` for a bad
    argument."""
    raise NotImplementedError


def run(cases: list[Case], exitfirst: bool = False) -> list[CaseResult]:
    """Run cases in order, one result per case run. A case whose `needs` did not all pass, or
    were not all collected, is skipped; a prompt that cannot be read is an error with every check skipped; a case whose
    checks were all skipped passes. With
    `exitfirst`, stop after the first failure or error and return the results so far."""
    raise NotImplementedError
