"""`expect`: checking what a task left. Specified in specs/evaluations.md, under Expect."""

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
    results: list[CheckResult] = []
    for expectation in expect:
        prefix, text, unread = "response", reply, []
        if expectation.with_path is not None:
            prefix = expectation.with_path
            try:
                text = read_text(folder / prefix)
            except PromptError as e:
                unread = [Finding(str(e))]
            results.append(result(Check("file", severity=expectation.severity), unread, prefix=prefix))
        if not unread:
            results += [run_check(c, Prompt(text), prefix) for c in expectation.checks]
    return tuple(results)
