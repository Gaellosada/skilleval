"""`expect`: checking what a task left. Specified in specs/evaluations.md, under Expect."""

from dataclasses import replace
from pathlib import Path

from skilleval.static import CheckResult, Finding, result, run_check
from skilleval.static.prompt import Prompt, PromptError, read_text
from skilleval.testfile import Check, Expectation


def check(expect: tuple[Expectation, ...], reply: str, folder: Path) -> tuple[CheckResult, ...]:
    """The results of one task's `expect`, in order: the checks on `reply`, the model's final
    message, under the prefix `response`, and those on each file of the workspace `folder`
    under its `with_path`.

    Each check runs through `static.run_check` on the text as an inline `Prompt`, so a
    constraint counts in a reply or a file as it does in a prompt. A file's results start
    with one named `file`, at the expectation's severity: a file that is missing or not
    UTF-8 text is its finding, and the file's checks are skipped.
    """
    return tuple(
        replace(checked, prefix=expectation.with_path or "response")
        for expectation in expect
        for checked in _results(expectation, reply, folder)
    )


def _results(expectation: Expectation, reply: str, folder: Path) -> list[CheckResult]:
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
