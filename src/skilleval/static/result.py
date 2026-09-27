"""What a check produces."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from skilleval.static.prompt import Prompt
from skilleval.testfile import Check

Status = Literal["passed", "failed", "warned", "skipped"]


@dataclass(frozen=True)
class Finding:
    """One problem, with the line it sits on when the check has one."""

    message: str
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """`failed` and `warned` mean findings at severity error or warn; `skipped` is a file-only
    check (`markdown_links`, `paths_exist`) on a text prompt. `detected` lists everything a
    heuristic check saw, findings or not: every path for `paths` and `paths_exist`, every
    URL for `urls`, the tag of every block for `code`, nothing for the others.

    `prefix` says what an evaluation checked, empty for a static check: `response` or the
    file's `with_path`, after the task's position when several ran. An evaluation also
    reports as a check, under the name of its key, what a test file sets without a check
    entry: `file`, `permissions`, `max_tokens`, `max_budget_usd`."""

    check: Check
    status: Status
    findings: tuple[Finding, ...] = ()
    detected: tuple[str, ...] = ()
    prefix: str = ""


# A check: the prompt and the normalised parameters in, its findings out.
CheckFunction = Callable[[Prompt, dict[str, Any]], list[Finding]]
