"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skilleval.testfile import Check


def parse_reference(reference: str, resolve: Callable[[str], Path]) -> tuple[Path, str]:
    """Split `path#name` into the template file's resolved path and the template name."""
    raise NotImplementedError


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """The union of a template's checks and a test's own: lint and format entries union by
    name keeping the stricter severity, constraints both stand, template entries first."""
    raise NotImplementedError
