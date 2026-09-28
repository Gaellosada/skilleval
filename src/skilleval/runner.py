"""Collection and execution: node ids, discovery, `needs`. Specified in specs/cli.md and specs/README.md."""

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skilleval import evaluation
from skilleval.evaluation import HarnessError
from skilleval.evaluation.workspace import locate
from skilleval.static import CheckResult, run_check
from skilleval.static.prompt import Prompt, PromptError, read
from skilleval.testfile import GlobPrompt, Test, TestFile, TextPrompt, load
from skilleval.testfile.paths import glob_to_regex

SKIPPED_DIRS = frozenset({"node_modules", "venv", "site-packages"})
Status = Literal["passed", "failed", "skipped", "error"]

_NODE_ID = re.compile(r"([^\[\]]+)(?:\[(.*)\])?")


class UsageError(Exception):
    """A bad invocation: a path that does not exist, a node id that matches nothing, brackets
    on a case that has none. Exit code 4."""


@dataclass(frozen=True)
class Case:
    """One runnable unit. `prompt_path` is the file behind it, None for an evaluation, a text
    prompt and an `include` that matched nothing (`test` tells them apart). `node_id` is
    `<file>::<id>` or `<file>::<id>[<prompt_path>]`, both paths posix and relative to the
    current directory. `siblings` is how many cases the test fanned out into at collection,
    this one included; `needs` compares against it at run time."""

    node_id: str
    file: TestFile
    test: Test
    siblings: int
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
    current directory. `keyword` keeps the node ids containing it. Raises `LoadError` for a bad
    file and `UsageError` for a bad argument."""
    files: dict[Path, list[Case]] = {}
    selected: set[str] = set()
    for arg in args or ["."]:
        paths, node = _paths_of(arg)
        for found in paths:
            key = found.resolve()
            if key not in files:
                files[key] = _cases(load(key))
            selected.update(case.node_id for case in _select(files[key], node, arg))
    return [
        case
        for cases in files.values()
        for case in cases
        if case.node_id in selected and (keyword is None or keyword in case.node_id)
    ]


def _paths_of(arg: str) -> tuple[list[Path], str]:
    """The files one argument names and its node part: a file as given, or every eval file
    below a directory, which takes no node part."""
    written, _, node = arg.partition("::")
    path = Path(written)
    if not path.exists():
        raise UsageError(f"{written}: no such file or directory")
    if not path.is_dir():
        return [path], node
    if node:
        raise UsageError(f"{arg}: a node id names a file, not a directory")
    return _discover(path), node


def _discover(directory: Path) -> list[Path]:
    """`*.eval.yml` and `*.eval.yaml` below `directory`, sorted, dot and vendored directories skipped."""
    return sorted(
        path
        for ext in ("yml", "yaml")
        for path in directory.rglob(f"*.eval.{ext}")
        if not any(
            p.startswith(".") or p in SKIPPED_DIRS for p in path.relative_to(directory).parts[:-1]
        )
    )


def _select(cases: list[Case], node: str, arg: str) -> list[Case]:
    """The cases of one file that `node` (`""`, `id` or `id[key]`) addresses."""
    if not node:
        return cases
    m = _NODE_ID.fullmatch(node)
    if m is None:
        raise UsageError(f"{arg}: a node id is <file>::<id> or <file>::<id>[<key>]")
    test_id, key = m[1], m[2]
    chosen = [case for case in cases if case.test.id == test_id]
    if not chosen:
        raise UsageError(f"{arg}: no test {test_id!r} in that file")
    if key is not None:
        if all(case.prompt_path is None for case in chosen):
            raise UsageError(f"{arg}: the case of test {test_id!r} takes no brackets")
        chosen = [case for case in chosen if case.node_id.endswith(f"[{key}]")]
        if not chosen:
            raise UsageError(f"{arg}: no case of test {test_id!r} is named {key!r}")
    return chosen


def _relative(path: Path) -> str:
    return Path(os.path.relpath(path, Path.cwd())).as_posix()


def _cases(file: TestFile) -> list[Case]:
    return [case for test in file.tests.values() for case in _fan_out(file, test)]


def _fan_out(file: TestFile, test: Test) -> list[Case]:
    """The cases of one test: one for an evaluation, a text prompt or a single file, one per
    match of a glob."""
    node_id = f"{_relative(file.path)}::{test.id}"
    if test.prompt is None or isinstance(test.prompt, TextPrompt):
        return [Case(node_id, file, test, 1)]
    if isinstance(test.prompt, GlobPrompt):
        excluded = [glob_to_regex(glob) for glob in test.prompt.exclude]
        matches = sorted(
            (path.relative_to(test.prompt.base).as_posix(), path)
            for path in test.prompt.base.glob(test.prompt.include)
            if path.is_file()
        )
        paths = [path for rel, path in matches if not any(x.match(rel) for x in excluded)]
        if not paths:
            return [Case(node_id, file, test, 1)]
    else:
        paths = [test.prompt.path]
    return [Case(f"{node_id}[{_relative(path)}]", file, test, len(paths), path) for path in paths]


def run(cases: list[Case], exitfirst: bool = False) -> list[CaseResult]:
    """Run cases in order, one result per case. A case whose `needs` did not all pass, or were
    not all collected, is skipped; a prompt that cannot be read is an error with every check
    skipped, as is an evaluation that cannot run; a case whose checks were all skipped passes.
    With `exitfirst`, stop after the first failure or error and return the results so far."""
    results: list[CaseResult] = []
    collected = Counter((case.file.path, case.test.id, case.siblings) for case in cases)
    complete = {(path, test) for (path, test, siblings), n in collected.items() if n >= siblings}
    not_passed: set[tuple[Path, str]] = set()
    for case in cases:
        unmet = (_unmet(case, need, complete, not_passed) for need in case.test.needs)
        reason = next((r for r in unmet if r), None)
        result = CaseResult(case, "skipped", reason=reason) if reason else _run_case(case)
        results.append(result)
        if result.status != "passed":
            not_passed.add((case.file.path, case.test.id))
        if exitfirst and result.status in ("failed", "error"):
            break
    return results


def _unmet(
    case: Case, need: str, complete: set[tuple[Path, str]], not_passed: set[tuple[Path, str]]
) -> str | None:
    """Why `need` does not unblock `case`: it did not pass, or not all of its cases were collected."""
    key = (case.file.path, need)
    if key in not_passed:
        return f"needs {need}"
    if key not in complete:
        return f"needs {need}, not selected"
    return None


def _run_case(case: Case) -> CaseResult:
    try:
        checks = _checks(case)
    except (PromptError, HarnessError) as e:
        return CaseResult(case, "error", reason=str(e))
    return CaseResult(case, "failed" if any(c.status == "failed" for c in checks) else "passed", checks)


def _checks(case: Case) -> tuple[CheckResult, ...]:
    """What one case leaves to report: an evaluation's results, or those of a static check's
    checks on its prompt. Raises `HarnessError` or `PromptError` when it cannot run."""
    if case.test.evaluation is not None:
        return evaluation.run(case.test.evaluation, locate(case.file.path, case.test.id))
    spec = case.test.prompt
    if isinstance(spec, TextPrompt):
        prompt = Prompt(spec.text, None, case.file.root)
    elif isinstance(spec, GlobPrompt) and case.prompt_path is None:
        raise PromptError(f"include {spec.include} matched nothing")
    else:
        assert case.prompt_path is not None  # a single file, or one glob match
        prompt = read(case.prompt_path, case.file.root)
    return tuple(run_check(check, prompt) for check in case.test.checks)
