"""The evaluation kind: running a setup on its tasks and checking what they leave. Specified
in specs/evaluations.md.

`run` drives the chain of tasks; `workspace` holds the folder the model works in, `harness`
gives it a task and `expect` checks the result.
"""

from pathlib import Path

from skilleval.evaluation import expect, harness, workspace
from skilleval.evaluation.harness import HarnessError
from skilleval.static import CheckResult
from skilleval.testfile import Evaluation

__all__ = ["HarnessError", "expect", "harness", "run", "workspace"]


def run(evaluation: Evaluation, folder: Path) -> tuple[CheckResult, ...]:
    """Run the tasks of `evaluation` in the workspace `folder` and return what they leave
    to report, in order.

    The workspace is filled by `workspace.fill`, then each task goes to `harness.ask`,
    dispatched at call time, with the reply to the task before it, so the chain is one
    conversation in one workspace. A task that ends is checked by `expect.check`. A task the
    harness stopped on a permission request leaves a failed result named `permissions` and
    its `expect` unchecked; the next task still runs. A reply whose tokens or cost are
    above a limit leaves a failed result named `max_tokens` or `max_budget_usd`, its `expect`
    unchecked, and ends the chain. When more than one task ran, the prefix of each result
    starts with the position of its task: `task 2`, `task 2: response`.

    Raises `HarnessError` for what keeps the test from running: as `harness.ask` does, and
    when the workspace cannot be filled.
    """
    raise NotImplementedError
