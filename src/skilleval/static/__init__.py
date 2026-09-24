"""The static-check kind: running checks against a prompt. Specified in specs/static-checking.md.

`CHECKS` maps a check name to its function, gathered from `lint`, `formats` and
`constraints`; `run_check` turns a function's findings into a `CheckResult`, filling
`detected` for the four heuristic checks and skipping the two file-only ones on a text prompt.
"""

from skilleval.static import constraints, formats, lint
from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, CheckResult, Finding
from skilleval.testfile import Check

__all__ = ["CHECKS", "CheckResult", "Finding", "run_check"]

CHECKS: dict[str, CheckFunction] = {**lint.CHECKS, **formats.CHECKS, **constraints.CHECKS}


def run_check(check: Check, prompt: Prompt) -> CheckResult:
    """Run one check against one prompt, dispatching through `CHECKS` at call time."""
    raise NotImplementedError
