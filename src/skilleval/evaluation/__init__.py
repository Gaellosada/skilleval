"""The evaluation kind: running a setup on its tasks and checking what they leave. Specified
in specs/evaluations.md.

`run` drives the chain of tasks; `config` reads the settings of whoever runs them,
`workspace` holds the folder the model works in and keeps what it leaves, `harness` gives it
a task and `expect` checks the result.
"""

from dataclasses import replace
from pathlib import Path

from skilleval.evaluation import config, expect, harness, workspace
from skilleval.evaluation.config import Config
from skilleval.evaluation.harness import HarnessError, Reply
from skilleval.static import CheckResult, Finding, result
from skilleval.testfile import Check, Evaluation, LoadError

__all__ = ["HarnessError", "config", "expect", "harness", "run", "workspace"]


def run(evaluation: Evaluation, file: Path, root: Path | None, test_id: str) -> tuple[CheckResult, ...]:
    """Run the tasks of `evaluation`, the test `test_id` of the test file `file` in the project
    `root` (None for a file declaring none), in the workspace `workspace.locate` names, and
    return what they leave to report, in order, as `_chain` does. When more than one task ran,
    the prefix of each result starts with the position of its task: `task 2`, `task 2:
    response`. Whatever the outcome, `workspace.keep` then keeps the results, with the
    transcripts of the tasks that returned.

    Raises `HarnessError` for what keeps the test from running: as `_settings` and `_chain`
    do, and when the results cannot be kept, unless one of them raised first, whose error wins.
    """
    folder = workspace.locate(file, test_id)
    replies: list[Reply] = []
    unkept = None
    try:
        ran = _chain(evaluation, _settings(file, root), folder, replies)
    finally:  # the chain's own error, when it raised one, goes on from here
        try:
            workspace.keep(folder, file, root, test_id, "".join(reply.transcript for reply in replies))
        except OSError as e:
            unkept = e
    if unkept:
        raise HarnessError(f"cannot keep the results in {workspace.results(file, root, test_id)}: {unkept}") from unkept
    if len(ran) == 1:
        return ran[0]
    return tuple(
        replace(r, prefix=f"task {n}: {r.prefix}".removesuffix(": ")) for n, results in enumerate(ran, 1) for r in results
    )


def _settings(file: Path, root: Path | None) -> Config:
    """The settings of whoever runs the test file `file`, of the project `root`, read from
    `config.NAME` in `workspace.home`, where a first run writes them. Raises `HarnessError`."""
    path = workspace.home(file, root) / config.NAME
    try:
        return config.load(path)
    except LoadError as e:
        raise HarnessError(str(e)) from e
    except OSError as e:
        raise HarnessError(f"cannot write the settings {path}: {e}") from e


def _chain(
    evaluation: Evaluation, settings: Config, folder: Path, replies: list[Reply]
) -> list[tuple[CheckResult, ...]]:
    """Run the tasks of `evaluation` in the workspace `folder`, with `settings`, appending
    each reply to `replies`, and return what each task leaves to report.

    The workspace is filled by `workspace.fill`, then each task goes to `harness.ask`,
    dispatched at call time, with the reply to the task before it, so the chain is one
    conversation in one workspace. A task that ends is checked by `expect.check`. A task in
    which the harness refused an action leaves a failed result named `permissions` and its
    `expect` unchecked; the next task still runs. A reply whose tokens or cost are above a
    limit leaves a failed result named `max_tokens` or `max_budget_usd`, its `expect`
    unchecked, and ends the chain.

    Raises `HarnessError` as `harness.ask` does, and when the workspace cannot be filled.
    """
    setup = evaluation.setup
    try:
        workspace.fill(folder, setup.working_folder)
    except OSError as e:
        raise HarnessError(f"cannot fill the workspace {folder}: {e}") from e
    ran: list[tuple[CheckResult, ...]] = []
    for task in evaluation.tasks:
        reply = harness.ask(task.text, setup, evaluation.model, folder, replies[-1] if replies else None,
                            config=settings, max_tokens=evaluation.max_tokens, max_budget_usd=evaluation.max_budget_usd)
        replies.append(reply)
        if over := _over(reply, evaluation):
            ran.append(over)
            break
        if reply.denied is not None:
            refused = Finding(f"{reply.denied} needed a permission, which the harness refused")
            ran.append((result(Check("permissions"), [refused]),))
        else:
            ran.append(expect.check(task.expect, reply.text, folder))
    return ran


def _over(reply: Reply, evaluation: Evaluation) -> tuple[CheckResult, ...]:
    """A failed result for each limit of `evaluation` that the conversation of `reply` is above."""
    used = (("max_tokens", reply.tokens, evaluation.max_tokens), ("max_budget_usd", reply.cost_usd, evaluation.max_budget_usd))
    return tuple(
        result(Check(name), [Finding(f"{spent} used, above the maximum of {limit}")])
        for name, spent, limit in used
        if limit is not None and spent > limit
    )
