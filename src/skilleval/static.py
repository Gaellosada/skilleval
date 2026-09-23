"""Running one static check against one prompt. Specified in specs/static-checking.md."""

from __future__ import annotations

from dataclasses import dataclass

from skilleval.prompt import Prompt
from skilleval.spec import Check


@dataclass(frozen=True)
class Finding:
    """One problem, with the line it sits on when the check has one."""

    message: str
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """`status` is `passed`, `failed` (findings, severity error), `warned` (findings, severity
    warn) or `skipped` (a file-only lint on a text prompt).
    `detected` lists everything a heuristic check saw, findings or not: every path for
    `paths` and `paths_exist`, every URL for `urls`, the tag of every block for `code`."""

    check: Check
    status: str
    findings: tuple[Finding, ...] = ()
    detected: tuple[str, ...] = ()


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt."""
    raise NotImplementedError
