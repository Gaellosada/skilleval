"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from dataclasses import replace
from functools import partial
from pathlib import Path

from skilleval.testfile import paths
from skilleval.testfile.checks import FAMILY, read_checks
from skilleval.testfile.document import (
    kind_of,
    known_keys,
    mapping,
    read_document,
    root_of,
)
from skilleval.testfile.schema import Check, at

TEMPLATE_KEYS = frozenset({"kind", "lint", "format", "constraints"})
_ORDER = ("lint", "format", "constraints")


def parse_reference(reference: str, resolve: paths.Resolver) -> tuple[Path, str]:
    """Split `path#name` into the template file's resolved path and the template name.
    Raises `ValueError` without a `#name`, or from `resolve`."""
    file, sep, name = reference.partition("#")
    if not (sep and name):
        raise ValueError(f"{reference!r} is not of the form path#template")
    return resolve(file), name


def read_templates(path: Path) -> dict[str, tuple[Check, ...]]:
    """The `templates` section of a file, validated, keyed by name. Reads that section alone
    and never the file's `tests`, so a file may use its own templates. Raises `LoadError`."""
    document = read_document(path)
    resolve = partial(paths.resolve, file=path, root=root_of(document, path))
    templates = {}
    for name, body in mapping(document.get("templates", {}), path, "templates").items():
        key = at("templates", name)
        body = mapping(body, path, key)
        known_keys(body, TEMPLATE_KEYS, path, key)
        kind_of(body, path, key)
        templates[name] = read_checks(body, path=path, key=key, resolve=resolve)
    return templates


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """The union of a template's checks and a test's own, lint then format then constraints:
    a lint or format named on both sides is one check at the stricter severity, in the
    template's position; constraints both stand, the template's first."""
    merged = list(template)
    for check in own:
        same = next((i for i, c in enumerate(merged) if c.name == check.name), None)
        if same is None or FAMILY[check.name] == "constraints":
            merged.append(check)
        elif check.severity == "error":
            merged[same] = replace(merged[same], severity="error")
    return tuple(sorted(merged, key=lambda c: _ORDER.index(FAMILY[c.name])))
