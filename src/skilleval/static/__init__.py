"""The static-check kind: running checks against a prompt. Specified in specs/static-checking.md.

`CHECKS` maps a check name to its function, gathered from `lint`, `formats` and
`constraints`; `run_check` turns a function's findings into a `CheckResult`, filling
`detected` for the four heuristic checks and skipping the two file-only ones on a text prompt.
"""

from skilleval.static import constraints, formats, lint
from skilleval.static import prompt as detect
from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, CheckResult, Finding, Status
from skilleval.testfile import Check

__all__ = ["CHECKS", "CheckResult", "Finding", "run_check"]

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


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt, dispatching through `CHECKS` at call time."""
    if check.name in FILE_ONLY and prompt.path is None:
        return CheckResult(check, "skipped")
    findings = tuple(CHECKS[check.name](prompt, check.params))
    status: Status = "passed"
    if findings:
        status = "failed" if check.severity == "error" else "warned"
    return CheckResult(check, status, findings, _detected(check.name, prompt))
