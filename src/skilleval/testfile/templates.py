"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from collections.abc import Callable
from pathlib import Path

from skilleval.testfile.checks import Check


def parse_reference(reference: str, resolve: Callable[[str], Path]) -> tuple[Path, str]:
    """Split `path#name` into the template file's resolved path and the template name."""
    raise NotImplementedError


def read_templates(path: Path) -> dict[str, tuple[Check, ...]]:
    """The `templates` section of a file, validated, keyed by name. Reads that section alone
    and never the file's `tests`, so a file may use its own templates. Raises `LoadError`."""
    raise NotImplementedError


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """The union of a template's checks and a test's own, lint then format then constraints:
    a lint or format named on both sides is one check at the stricter severity, in the
    template's position; constraints both stand, the template's first."""
    raise NotImplementedError
