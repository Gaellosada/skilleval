"""The evaluation kind: running a setup on its tasks and checking what they leave. Specified
in specs/evaluations.md.

`run` drives the chain of tasks; `workspace` holds the folder the model works in, `harness`
gives it a task and `expect` checks the result.
"""

from dataclasses import replace
from pathlib import Path

from skilleval.evaluation import expect, harness, workspace
from skilleval.evaluation.harness import HarnessError, Reply
from skilleval.static import CheckResult, Finding, result
from skilleval.testfile import Check, Evaluation

__all__ = ["HarnessError", "expect", "harness", "run", "workspace"]


def run(evaluation: Evaluation, folder: Path) -> tuple[CheckResult, ...]:
    """Run the tasks of `evaluation` in the workspace `folder` and return what they leave
    to report, in order.

    The workspace is filled by `workspace.fill`, then each task goes to `harness.ask`,
    dispatched at call time, with the reply to the task before it, so the chain is one
    conversation in one workspace. A task that ends is checked by `expect.check`. A task in
    which the harness refused an action leaves a failed result named `permissions` and
    its `expect` unchecked; the next task still runs. A reply whose tokens or cost are
    above a limit leaves a failed result named `max_tokens` or `max_budget_usd`, its `expect`
    unchecked, and ends the chain. When more than one task ran, the prefix of each result
    starts with the position of its task: `task 2`, `task 2: response`.

    Raises `HarnessError` for what keeps the test from running: as `harness.ask` does, and
    when the workspace cannot be filled.
    """
    setup = evaluation.setup
    try:
        workspace.fill(folder, setup.working_folder)
    except OSError as e:
        raise HarnessError(f"cannot fill the workspace {folder}: {e}") from e
    ran: list[tuple[CheckResult, ...]] = []
    reply = None
    for task in evaluation.tasks:
        reply = harness.ask(task.text, setup, evaluation.model, folder, reply,
                            max_tokens=evaluation.max_tokens, max_budget_usd=evaluation.max_budget_usd)
        if over := _over(reply, evaluation):
            ran.append(over)
            break
        if reply.denied is not None:
            refused = Finding(f"{reply.denied} needed a permission, which the harness refused")
            ran.append((result(Check("permissions"), [refused]),))
        else:
            ran.append(expect.check(task.expect, reply.text, folder))
    if len(ran) == 1:
        return ran[0]
    return tuple(
        replace(r, prefix=f"task {n}: {r.prefix}".removesuffix(": ")) for n, results in enumerate(ran, 1) for r in results
    )


def _over(reply: Reply, evaluation: Evaluation) -> tuple[CheckResult, ...]:
    """A failed result for each limit of `evaluation` that the conversation of `reply` is above."""
    used = (("max_tokens", reply.tokens, evaluation.max_tokens), ("max_budget_usd", reply.cost_usd, evaluation.max_budget_usd))
    return tuple(
        result(Check(name), [Finding(f"{spent} used, above the maximum of {limit}")])
        for name, spent, limit in used
        if limit is not None and spent > limit
    )
