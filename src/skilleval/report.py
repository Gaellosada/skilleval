"""Terminal output in pytest's shape. Specified in specs/cli.md."""

from collections import Counter

from skilleval.runner import CaseResult

WIDTH = 80
PROGRESS = {"passed": ".", "failed": "F", "error": "E", "skipped": "s"}


def render(results: list[CaseResult], verbosity: int, seconds: float) -> str:
    """The run as text: the cases (progress per file at verbosity 0, one line per case at 1,
    nothing at -1); then the FAILURES and ERRORS sections; then the summary line with
    counts. Findings print as `<check>: <message>`, `(line N)` when the finding has a line
    and `[warn]` when the check is a warning."""
    lines: list[str] = []
    if verbosity >= 0:
        lines += [f"collected {len(results)} cases", ""]
    lines += _cases(results, verbosity)
    failed = [r for r in results if r.status == "failed"]
    errors = [r for r in results if r.status == "error"]
    if failed:
        lines += ["", " FAILURES ".center(WIDTH, "=")]
        for r in failed:
            lines += [f"{r.case.node_id} FAILED", *_findings(r)]
    if errors:
        lines += ["", " ERRORS ".center(WIDTH, "=")]
        for r in errors:
            lines += [f"{r.case.node_id} ERROR", f"  {r.reason}; {len(r.case.test.checks)} checks skipped"]
    lines += ["", f" {_summary(results)} in {seconds:.2f}s ".center(WIDTH, "=")]
    return "\n".join(lines)


def _cases(results: list[CaseResult], verbosity: int) -> list[str]:
    """Progress per file at verbosity 0; at 1, one line per case with its findings and the
    items each check detected under it; nothing at -1."""
    lines: list[str] = []
    if verbosity == 0:
        progress: dict[str, str] = {}
        for r in results:
            file = r.case.node_id.split("::")[0]
            progress[file] = progress.get(file, "") + PROGRESS[r.status]
        lines += [f"{file} {chars}" for file, chars in progress.items()]
    elif verbosity == 1:
        for r in results:
            suffix = f" ({r.reason})" if r.status == "skipped" else ""
            lines += [f"{r.case.node_id} {r.status.upper()}{suffix}", *_findings(r)]
            lines += [
                f"  {c.check.name}: detected {', '.join(c.detected)}"
                for c in r.checks
                if c.detected
            ]
    return lines


def _findings(result: CaseResult) -> list[str]:
    return [
        f"  {c.check.name}: {f.message}"
        + (f" (line {f.line})" if f.line else "")
        + (" [warn]" if c.status == "warned" else "")
        for c in result.checks
        if c.status in ("failed", "warned")
        for f in c.findings
    ]


def _summary(results: list[CaseResult]) -> str:
    counts: Counter[str] = Counter(r.status for r in results)
    counts["warning"] = sum(c.status == "warned" for r in results for c in r.checks)
    parts = []
    for word in ("failed", "passed", "skipped", "error", "warning"):
        if n := counts[word]:
            parts.append(f"{n} {word}{'s' if n > 1 and word in ('error', 'warning') else ''}")
    return ", ".join(parts)
