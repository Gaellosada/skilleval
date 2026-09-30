"""Terminal output in pytest's shape, printed as the cases run. Specified in specs/cli.md."""

from collections import Counter
from dataclasses import dataclass, field

from skilleval.evaluation import workspace
from skilleval.runner import Case, CaseResult
from skilleval.static import CheckResult
from skilleval.testfile import Run, Test

WIDTH = 80
PROGRESS = {"passed": ".", "failed": "F", "error": "E", "skipped": "s"}


@dataclass
class Report:
    """The run as text, printed as it goes, each write flushed: `collected` opens it, `started`
    and `finished` are the callbacks of `runner.run`, `ended` prints the FAILURES and ERRORS
    sections and the summary line with counts. At verbosity 0, a file's name as its first case
    starts, then a progress character as each case ends; at 1, a case's node id as it starts,
    then its status, its findings and the items each check detected; at -1, nothing until the
    end. Findings print as `<check>: <message>`, after `<prefix>: ` when the result has one,
    with `(line N)` when the finding has a line and `[warn]` when the check is a warning, both
    ending the message's first line, the rest of a message of several lines following. An
    evaluation that ran names its workspace last under its case."""

    verbosity: int
    file: str | None = field(default=None, init=False)  # the file whose progress line is open, at verbosity 0

    def collected(self, n: int) -> None:
        if self.verbosity >= 0:
            _write(f"collected {n} cases\n\n")

    def started(self, case: Case) -> None:
        file = case.node_id.split("::")[0]
        if self.verbosity == 1:
            _write(f"{case.node_id} ")
        elif self.verbosity == 0 and file != self.file:
            _write(f"\n{file} " if self.file else f"{file} ")
            self.file = file

    def finished(self, r: CaseResult) -> None:
        if self.verbosity == 0:
            _write(PROGRESS[r.status])
        elif self.verbosity == 1:
            suffix = f" ({r.reason})" if r.status == "skipped" else ""
            lines = [f"{r.status.upper()}{suffix}", *_findings(r)]
            lines += [f"  {_label(c)}: detected {', '.join(c.detected)}" for c in r.checks if c.detected]
            _write("".join(f"{line}\n" for line in [*lines, *_workspace(r)]))

    def ended(self, results: list[CaseResult], seconds: float) -> None:
        lines: list[str] = []
        failed = [r for r in results if r.status == "failed"]
        errors = [r for r in results if r.status == "error"]
        if failed:
            lines += ["", " FAILURES ".center(WIDTH, "=")]
            for r in failed:
                lines += [f"{r.case.node_id} FAILED", *_findings(r), *_workspace(r)]
        if errors:
            lines += ["", " ERRORS ".center(WIDTH, "=")]
            for r in errors:
                n = _count(r.case.test)
                reason = "  " + _ending_first_line(r.reason or "", f"; {n} check{'s' * (n != 1)} skipped")
                lines += [f"{r.case.node_id} ERROR", reason, *_workspace(r)]
        lines += ["", f" {_summary(results)} in {seconds:.2f}s ".center(WIDTH, "=")]
        _write("\n" * (self.file is not None) + "\n".join(lines) + "\n")


def _write(text: str) -> None:
    print(text, end="", flush=True)


def _workspace(result: CaseResult) -> list[str]:
    """The line naming the workspace of an evaluation that ran; nothing for a skipped one,
    which touched none, or for another kind."""
    case = result.case
    if case.test.evaluation is None or result.status == "skipped":
        return []
    return [f"  workspace: {workspace.results(case.file.path, case.file.root, case.test.id) / 'workspace'}"]


def _count(test: Test) -> int:
    """How many checks a test holds: for an evaluation those of every task, the existence of
    each file and each `run` among them."""
    if test.evaluation is None:
        return len(test.checks)
    return sum(
        1 if isinstance(e, Run) else len(e.checks) + (e.with_path is not None)
        for task in test.evaluation.tasks for e in task.expect
    )


def _label(result: CheckResult) -> str:
    """The name of a check, after the prefix of its result when it has one."""
    return f"{result.prefix}: {result.check.name}" if result.prefix else result.check.name


def _findings(result: CaseResult) -> list[str]:
    return [
        f"  {_label(c)}: "
        + _ending_first_line(f.message, (f" (line {f.line})" if f.line else "") + (" [warn]" if c.status == "warned" else ""))
        for c in result.checks
        if c.status in ("failed", "warned")
        for f in c.findings
    ]


def _ending_first_line(message: str, suffix: str) -> str:
    """`message` with `suffix` at the end of its first line, the lines after it as written."""
    first, newline, rest = message.partition("\n")
    return first + suffix + newline + rest


def _summary(results: list[CaseResult]) -> str:
    counts: Counter[str] = Counter(r.status for r in results)
    counts["warning"] = sum(c.status == "warned" for r in results for c in r.checks)
    parts = []
    for word in ("failed", "passed", "skipped", "error", "warning"):
        if n := counts[word]:
            parts.append(f"{n} {word}{'s' if n > 1 and word in ('error', 'warning') else ''}")
    return ", ".join(parts)
