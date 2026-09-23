"""The static-check kind: running checks against a prompt. Specified in specs/static-checking.md.

`CHECKS` maps a check name to its function, gathered from `lint`, `formats` and
`constraints`. A check function takes the prompt and the normalised parameters and returns
its findings and everything it detected; `run_check` turns that into a `CheckResult`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from skilleval.static import constraints, formats, lint
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check


@dataclass(frozen=True)
class Finding:
    """One problem, with the line it sits on when the check has one."""

    message: str
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """`status` is `passed`, `failed` (findings, severity error), `warned` (findings, severity
    warn) or `skipped` (a file-only check on a text prompt). `detected` lists everything a
    heuristic check saw, findings or not: every path for `paths` and `paths_exist`, every
    URL for `urls`, the tag of every block for `code`."""

    check: Check
    status: str
    findings: tuple[Finding, ...] = ()
    detected: tuple[str, ...] = ()


CHECKS: dict[str, Callable[[Prompt, dict], tuple[list[Finding], list[str]]]] = {
    **lint.CHECKS, **formats.CHECKS, **constraints.CHECKS,
}
FILE_ONLY = frozenset({"markdown_links", "paths_exist"})  # skipped on a text prompt


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt."""
    raise NotImplementedError
