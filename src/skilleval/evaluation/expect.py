"""`expect`: checking what a task left. Specified in specs/evaluations.md, under Expect."""

import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
from collections import deque
from dataclasses import replace
from pathlib import Path

from skilleval.evaluation.harness import HarnessError
from skilleval.static import CheckResult, Finding, result, run_check
from skilleval.static.prompt import Prompt, PromptError, read_text
from skilleval.testfile import Check, Expectation, Run

TAIL = 20  # the lines of output a `run` failure ends with
BROKEN = 99  # the exit code of a `run` command that could not check


def check(expect: tuple[Expectation | Run, ...], reply: str, folder: Path) -> tuple[CheckResult, ...]:
    """The results of one task's `expect`, in order: the checks on `reply`, the model's final
    message, under the prefix `response`, those on each file of the workspace `folder` under
    its `with_path`, and each `Run` under `run`, as `_run` checks it.

    Each check runs through `static.run_check` on the text as an inline `Prompt`, so a
    constraint counts in a reply or a file as it does in a prompt. A file's results start
    with one named `file`, at the expectation's severity: a file that is missing or not
    UTF-8 text is its finding, and the file's checks are skipped.

    Raises `HarnessError` as `_run` does.
    """
    return tuple(
        replace(checked, prefix="run" if isinstance(expectation, Run) else expectation.with_path or "response")
        for expectation in expect
        for checked in _results(expectation, reply, folder)
    )


def _results(expectation: Expectation | Run, reply: str, folder: Path) -> list[CheckResult]:
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


def _run(run: Run, folder: Path) -> CheckResult:
    """The result of `run`, named after the first line of its command: bash runs it in a copy
    of the workspace `folder`, beside it, deleted once it ends, with an empty standard input
    and `SKILLEVAL_FILE_DIR` added to the environment. Exit 0 passes; any other code fails,
    and so does running over the timeout, the finding ending with the last `TAIL` lines of
    output. Its process group is killed once it exits or runs over, so nothing it started
    outlives the copy.

    Raises `HarnessError`, naming the command, when no bash is on the `PATH`, when the copy
    cannot be made or run in, and on exit `BROKEN`, ending with the same lines.
    """
    name = run.command.splitlines()[0]
    bash = shutil.which("bash")
    if bash is None:
        raise HarnessError(f"run: {name}: no bash on the PATH to run it")
    command = [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", run.command]
    env = os.environ | {"SKILLEVAL_FILE_DIR": str(run.directory)}
    with tempfile.TemporaryDirectory(dir=folder.parent) as copy, tempfile.TemporaryFile() as output:
        try:
            shutil.copytree(folder, copy, symlinks=True, dirs_exist_ok=True)
            process = subprocess.Popen(command, cwd=copy, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            raise HarnessError(f"run: {name}: cannot run it in a copy of the workspace {folder}: {e}") from e
        try:
            code = process.wait(run.timeout)
        except subprocess.TimeoutExpired:
            code = None
        finally:
            with contextlib.suppress(ProcessLookupError):  # nothing of the group is left
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        output.seek(0)
        tail = "".join(f"\n    {line.decode(errors='replace').rstrip()}" for line in deque(output, TAIL))
    if code == BROKEN:
        raise HarnessError(f"run: {name}: exited with {BROKEN}, the command could not check{tail}")
    verdict = f"ran over {run.timeout:g} s" if code is None else f"exited with {code}"
    return result(Check(name, severity=run.severity), [] if code == 0 else [Finding(verdict + tail)])
