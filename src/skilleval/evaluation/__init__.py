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


def run(evaluation: Evaluation, file: Path, root: Path | None, test_id: str) -> tuple[CheckResult, ...]:
    """Run the tasks of `evaluation`, the test `test_id` of the test file `file` in the project
    `root`, and return what they leave to report, in order.

    The workspace, which `workspace.locate` names, is filled by `workspace.fill`, then each
    task goes to `harness.ask`, dispatched at call time, with the reply to the task before it,
    so the chain is one conversation in one workspace. A task that ends is checked by
    `expect.check`. A task in which the harness refused an action leaves a failed result
    named `permissions` and its `expect` unchecked; the next task still runs. A reply whose tokens or cost are
    above a limit leaves a failed result named `max_tokens` or `max_budget_usd`, its `expect`
    unchecked, and ends the chain. When more than one task ran, the prefix of each result
    starts with the position of its task: `task 2`, `task 2: response`.

    Raises `HarnessError` for what keeps the test from running: as `harness.ask` does, and
    when the workspace cannot be filled.

    Whatever the outcome, `workspace.keep` then keeps the results, with the transcripts of
    the tasks that returned.
    """
    setup, folder = evaluation.setup, workspace.locate(file, test_id)
    ran: list[tuple[CheckResult, ...]] = []
    replies: list[Reply] = []
    try:
        try:
            workspace.fill(folder, setup.working_folder)
        except OSError as e:
            raise HarnessError(f"cannot fill the workspace {folder}: {e}") from e
        for task in evaluation.tasks:
            reply = harness.ask(task.text, setup, evaluation.model, folder, replies[-1] if replies else None,
                                max_tokens=evaluation.max_tokens, max_budget_usd=evaluation.max_budget_usd)
            replies.append(reply)
            if over := _over(reply, evaluation):
                ran.append(over)
                break
            if reply.denied is not None:
                refused = Finding(f"{reply.denied} needed a permission, which the harness refused")
                ran.append((result(Check("permissions"), [refused]),))
            else:
                ran.append(expect.check(task.expect, reply.text, folder))
    finally:
        workspace.keep(file, root, test_id, "".join(reply.transcript for reply in replies))
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
