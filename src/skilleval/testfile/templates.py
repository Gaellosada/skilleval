"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from skilleval.testfile import paths
from skilleval.testfile.checks import FAMILY, read_checks
from skilleval.testfile.document import (
    kind_of,
    known_keys,
    mapping,
    root_of,
    section,
)
from skilleval.testfile.schema import Check, at

TEMPLATE_KEYS = frozenset({"kind", "lint", "format", "constraints"})
_ORDER = ("lint", "format", "constraints")
Template = tuple[str, tuple[Check, ...]]  # its kind and its checks


def parse_reference(reference: str, resolve: paths.Resolver) -> tuple[Path, str]:
    """Split `path#name` into the template file's resolved path and the template name.
    Raises `ValueError` without a `#name`, or from `resolve`."""
    file, sep, name = reference.partition("#")
    if not (sep and name):
        raise ValueError(f"{reference!r} is not of the form path#template")
    return resolve(file), name


def read_templates(document: dict[str, Any], path: Path) -> dict[str, Template]:
    """The `templates` section of the file at `path`, read into `document`, validated and
    keyed by name. Reads that section alone and never the file's `tests`, so a file may use
    its own templates. Raises `LoadError`."""
    resolve = partial(paths.resolve, file=path, root=root_of(document, path))
    templates = {}
    for name, body in section(document, "templates", path).items():
        key = at("templates", name)
        body = mapping(body, path, key)
        known_keys(body, TEMPLATE_KEYS, path, key)
        templates[name] = kind_of(body, path, key), read_checks(body, path=path, key=key, resolve=resolve)
    return templates


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """The union of a template's checks and a test's own, lint then format then constraints:
    a format in `own` replaces the template's; a lint named on both sides is one check at the
    stricter severity, in the template's position; constraints both stand, the template's first."""
    if any(FAMILY[c.name] == "format" for c in own):
        template = tuple(c for c in template if FAMILY[c.name] != "format")
    merged = list(template)
    for check in own:
        same = next((i for i, c in enumerate(merged) if c.name == check.name), None)
        if same is None or FAMILY[check.name] == "constraints":
            merged.append(check)
        elif check.severity == "error":
            merged[same] = replace(merged[same], severity="error")
    return tuple(sorted(merged, key=lambda c: _ORDER.index(FAMILY[c.name])))
