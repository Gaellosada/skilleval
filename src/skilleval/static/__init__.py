"""The static-check kind: running checks against a prompt. Specified in specs/static-checking.md.

`CHECKS` maps a check name to its function, gathered from `lint`, `formats` and
`constraints`; `run_check` turns a function's findings into a `CheckResult`, filling
`detected` for the four heuristic checks and skipping the two file-only ones on a text prompt.
"""

from collections.abc import Iterable

from skilleval.static import constraints, formats, lint
from skilleval.static import prompt as detect
from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, CheckResult, Finding, Status
from skilleval.testfile import Check

__all__ = ["CHECKS", "CheckResult", "Finding", "result", "run_check"]

CHECKS: dict[str, CheckFunction] = {**lint.CHECKS, **formats.CHECKS, **constraints.CHECKS}

FILE_ONLY = frozenset({"markdown_links", "paths_exist"})


def _detected(name: str, prompt: Prompt) -> tuple[str, ...]:
    if name in ("paths", "paths_exist"):
        return tuple(t.text for t in detect.paths(prompt))
    if name == "urls":
        return tuple(t.text for t in detect.urls(prompt))
    if name == "code":
        return tuple(f.lang for f in detect.fences(prompt))
    return ()


def result(check: Check, findings: Iterable[Finding], detected: tuple[str, ...] = ()) -> CheckResult:
    """What `check` leaves to report: `passed` without findings, else `failed`, or `warned`
    at severity `warn`."""
    findings = tuple(findings)
    status: Status = "passed"
    if findings:
        status = "warned" if check.severity == "warn" else "failed"
    return CheckResult(check, status, findings, detected)


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt, dispatching through `CHECKS` at call time."""
    if check.name in FILE_ONLY and prompt.path is None:
        return CheckResult(check, "skipped")
    return result(check, CHECKS[check.name](prompt, check.params), _detected(check.name, prompt))
