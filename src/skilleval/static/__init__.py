"""The static-check kind: running checks against a prompt. Specified in specs/static-checking.md.

`CHECKS` maps a check name to its function, gathered from `lint`, `formats` and
`constraints`; `run_check` turns a function's output into a `CheckResult`.
"""

from __future__ import annotations

from skilleval.static import constraints, formats, lint
from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, CheckResult, Finding
from skilleval.testfile import Check

__all__ = ["CHECKS", "FILE_ONLY", "CheckResult", "Finding", "run_check"]

CHECKS: dict[str, CheckFunction] = {**lint.CHECKS, **formats.CHECKS, **constraints.CHECKS}
FILE_ONLY = frozenset({"markdown_links", "paths_exist"})  # skipped on a text prompt


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt."""
    raise NotImplementedError
