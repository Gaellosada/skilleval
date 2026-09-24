"""Collection and execution: node ids, discovery, `needs`. Specified in specs/cli.md and specs/README.md."""

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
    current directory. `keyword` keeps the node ids containing it. Raises `LoadError` for a bad
    file and `UsageError` for a bad argument."""
    files: dict[Path, list[Case]] = {}
    selected: set[str] = set()
    for arg in args or ["."]:
        written, _, node = arg.partition("::")
        path = Path(written)
        if not path.exists():
            raise UsageError(f"{written}: no such file or directory")
        if path.is_dir() and node:
            raise UsageError(f"{arg}: a node id names a file, not a directory")
        for found in _discover(path) if path.is_dir() else [path]:
            cases = files.setdefault(found.resolve(), _cases(load(found.resolve())))
            selected.update(case.node_id for case in _select(cases, node, arg))
    return [
        case
        for cases in files.values()
        for case in cases
        if case.node_id in selected and (keyword is None or keyword in case.node_id)
    ]


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
    id, key = m[1], m[2]
    chosen = [case for case in cases if case.test.id == id]
    if not chosen:
        raise UsageError(f"{arg}: no test {id!r} in that file")
    if key is not None:
        chosen = [case for case in chosen if case.node_id.endswith(f"[{key}]")]
        if not chosen:
            raise UsageError(f"{arg}: no case of test {id!r} is named {key!r}")
    return chosen


def _relative(path: Path) -> str:
    return Path(os.path.relpath(path, Path.cwd())).as_posix()


def _cases(file: TestFile) -> list[Case]:
    return [case for test in file.tests.values() for case in _fan_out(file, test)]


def _fan_out(file: TestFile, test: Test) -> list[Case]:
    """The cases of one test: one for a text prompt or a single file, one per match of a glob."""
    node_id = f"{_relative(file.path)}::{test.id}"
    if isinstance(test.prompt, TextPrompt):
        return [Case(node_id, file, test)]
    if isinstance(test.prompt, GlobPrompt):
        excluded = [glob_to_regex(glob) for glob in test.prompt.exclude]
        matches = sorted(
            (path.relative_to(test.prompt.base).as_posix(), path)
            for path in test.prompt.base.glob(test.prompt.include)
            if path.is_file()
        )
        paths = [path for rel, path in matches if not any(x.match(rel) for x in excluded)]
        if not paths:
            return [Case(node_id, file, test)]
    else:
        paths = [test.prompt.path]
    return [Case(f"{node_id}[{_relative(path)}]", file, test, path) for path in paths]


def run(cases: list[Case], exitfirst: bool = False) -> list[CaseResult]:
    """Run cases in order, one result per case. A case whose `needs` did not all pass, or were
    not all collected, is skipped; a prompt that cannot be read is an error with every check
    skipped; a case whose checks were all skipped passes. With `exitfirst`, stop after the first
    failure or error and return the results so far."""
    results: list[CaseResult] = []
    collected = Counter((case.file.path, case.test.id) for case in cases)
    not_passed: set[tuple[Path, str]] = set()
    for case in cases:
        unmet = (_unmet(case, need, collected, not_passed) for need in case.test.needs)
        reason = next((r for r in unmet if r), None)
        result = CaseResult(case, "skipped", reason=reason) if reason else _run_case(case)
        results.append(result)
        if result.status != "passed":
            not_passed.add((case.file.path, case.test.id))
        if exitfirst and result.status in ("failed", "error"):
            break
    return results


def _unmet(
    case: Case, need: str, collected: Counter[tuple[Path, str]], not_passed: set[tuple[Path, str]]
) -> str | None:
    """Why `need` does not unblock `case`: it did not pass, or not all of its cases were collected."""
    key = (case.file.path, need)
    if key in not_passed:
        return f"needs {need}"
    if collected[key] < len(_fan_out(case.file, case.file.tests[need])):
        return f"needs {need}, not selected"
    return None


def _run_case(case: Case) -> CaseResult:
    spec = case.test.prompt
    if isinstance(spec, TextPrompt):
        prompt = Prompt(spec.text, None, case.file.root)
    elif isinstance(spec, GlobPrompt) and case.prompt_path is None:
        return CaseResult(case, "error", reason=f"include {spec.include} matched nothing")
    else:
        assert case.prompt_path is not None  # a single file, or one glob match
        try:
            prompt = read(case.prompt_path, case.file.root)
        except PromptError as e:
            return CaseResult(case, "error", reason=str(e))
    checks = tuple(run_check(check, prompt) for check in case.test.checks)
    return CaseResult(case, "failed" if any(c.status == "failed" for c in checks) else "passed", checks)
