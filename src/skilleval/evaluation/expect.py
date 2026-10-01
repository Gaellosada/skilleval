"""`expect`: checking what a task left. Specified in specs/evaluations.md, under Expect."""

import contextlib
import math
import os
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from skilleval.evaluation.harness import HarnessError
from skilleval.evaluation.harness.base import tail
from skilleval.static import CheckResult, Finding, result, run_check
from skilleval.static.prompt import Prompt, PromptError, read_text
from skilleval.testfile import Block, Check, Expectation, Judge, Run, Usage

BROKEN = 99  # the exit code of a `run` command that could not check


def check(
    expect: tuple[Block, ...], reply: str, folder: Path, ask: Callable[[Judge], CheckResult],
    *, seconds: float, output_tokens: int,
) -> tuple[CheckResult, ...]:
    """The results of one task's `expect`, in order: the checks on `reply`, the model's final
    message, under the prefix `response`, those on each file of the workspace `folder` under
    its `with_path`, each `Run` under `run`, as `_run` checks it, each `Judge` under `judge`,
    as `ask` answers it, and each `Usage` as `_usage` checks the task's `seconds` and
    `output_tokens` against it.

    Each check runs through `static.run_check` on the text as an inline `Prompt`, so a
    constraint counts in a reply or a file as it does in a prompt. A file's results start
    with one named `file`, at the expectation's severity: a file that is missing or not
    UTF-8 text is its finding, and the file's checks are skipped.

    Raises `HarnessError` as `_run` and `ask` do.
    """
    return tuple(
        replace(checked, prefix=_prefix(expectation))
        for expectation in expect
        for checked in _results(expectation, reply, folder, ask, seconds, output_tokens)
    )


def _prefix(expectation: Block) -> str:
    if isinstance(expectation, Expectation):
        return expectation.with_path or "response"
    if isinstance(expectation, Usage):
        return ""  # its result is named `usage`, as a limit's is named after the limit
    return "run" if isinstance(expectation, Run) else "judge"


def _results(
    expectation: Block, reply: str, folder: Path, ask: Callable[[Judge], CheckResult],
    seconds: float, output_tokens: int,
) -> list[CheckResult]:
    if isinstance(expectation, Usage):
        return [_usage(expectation, seconds, output_tokens)]
    if isinstance(expectation, Judge):
        return [ask(expectation)]
    if isinstance(expectation, Run):
        return [_run(expectation, folder)]
    text = reply
    exists = []
    if expectation.with_path is not None:
        file = Check("file", severity=expectation.severity)
        try:
            text = read_text(folder / expectation.with_path)
        except PromptError as e:
            return [result(file, [Finding(str(e))])]
        exists = [result(file, [])]
    return exists + [run_check(c, Prompt(text)) for c in expectation.checks]


def _usage(usage: Usage, seconds: float, output_tokens: int) -> CheckResult:
    """The result of `usage`, named `usage`, for a task that took `seconds` and in which the
    model wrote `output_tokens`: one finding for each bound the task is above, the seconds
    shown to the tenth, rounded up, so that they never show at the bound they are above."""
    used = (
        ("max_seconds", seconds, f"{math.ceil(seconds * 10) / 10:.1f}", usage.max_seconds),
        ("max_output_tokens", output_tokens, str(output_tokens), usage.max_output_tokens),
    )
    return result(Check("usage", severity=usage.severity), [
        Finding(f"{name}: {shown} used, above the maximum of {bound}")
        for name, spent, shown, bound in used
        if bound is not None and spent > bound
    ])


def _run(run: Run, folder: Path) -> CheckResult:
    """The result of `run`, named after the first line of its command that is not blank: bash
    runs it in a copy of the workspace `folder`, beside it, deleted once it ends, with an
    empty standard input and `SKILLEVAL_FILE_DIR` added to the environment. Exit 0 passes;
    any other code fails, and so do a signal killing bash and running over the timeout, the
    finding ending with the `tail` of the output. A workspace that cannot be copied fails,
    the command not run. Its process group is killed once it exits or runs over, so nothing
    it started in the group outlives the copy.

    Raises `HarnessError`, naming the command, when no bash is on the `PATH` or it cannot
    start, when the copy cannot be created or deleted, and on exit `BROKEN`, ending with the
    same tail.
    """
    name = first_line(run.command)
    checked = Check(name, severity=run.severity)
    bash = shutil.which("bash")
    if bash is None:
        raise HarnessError(f"run: {name}: no bash on the PATH to run it")
    command = [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", run.command]
    env = os.environ | {"SKILLEVAL_FILE_DIR": str(run.directory)}
    try:
        with tempfile.TemporaryDirectory(dir=folder.parent) as copy, tempfile.TemporaryFile() as output:
            try:
                shutil.copytree(folder, copy, symlinks=True, dirs_exist_ok=True)
            except OSError as e:  # the model's doing, such as a file it left unreadable
                why = "; ".join(reason for *_, reason in e.args[0]) if isinstance(e, shutil.Error) else e
                return result(checked, [Finding(f"the workspace cannot be copied: {why}")])
            process = subprocess.Popen(command, cwd=copy, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(run.timeout)
            except subprocess.TimeoutExpired:
                code = None
            finally:
                with contextlib.suppress(ProcessLookupError, PermissionError):  # none of the group left, or not ours
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            printed = tail(output)
    except OSError as e:
        raise HarnessError(f"run: {name}: cannot run it in a copy of the workspace, or delete the copy: {e}") from e
    if code == BROKEN:
        raise HarnessError(f"run: {name}: exited with {BROKEN}, the command could not check{printed}")
    if code is None:
        verdict = f"ran over {run.timeout} s"
    else:
        verdict = f"killed by signal {-code}" if code < 0 else f"exited with {code}"
    return result(checked, [] if code == 0 else [Finding(verdict + printed)])


def first_line(text: str) -> str:
    """The first line of `text` that is not blank, stripped: what a `run` or a `judge` block reports under."""
    return next(line.strip() for line in text.splitlines() if line.strip())

