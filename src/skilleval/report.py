"""Terminal output in pytest's shape. Specified in specs/cli.md."""

from skilleval.runner import CaseResult


def render(results: list[CaseResult], verbosity: int, seconds: float) -> str:
    """The run as text: progress per file (verbosity 0) or one line per case (1), nothing but
    the sections below at -1; then the FAILURES and ERRORS sections, then the summary line
    with counts. Findings print as `<check>: <message>`, `(line N)` when the finding has a
    line and `[warn]` when the check is a warning; detected items print under their check
    at verbosity 1."""
    raise NotImplementedError
