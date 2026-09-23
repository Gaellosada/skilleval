"""What a check produces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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


CheckFunction = Callable[[Prompt, dict], tuple[list[Finding], list[str]]]
"""A check: the prompt and the normalised parameters in, its findings and what it detected out."""
