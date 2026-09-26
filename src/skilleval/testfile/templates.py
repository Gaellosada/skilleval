"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

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
ADDITIVE = frozenset({"contains", "contains_any", "contains_none", "matches", "matches_any", "matches_none"})
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
    """A template's checks with a test's own merged in, lint then format then constraints:
    a format in `own` replaces the template's; an `ADDITIVE` entry is added; any other entry
    named on both sides overrides each of the template's in place, parameter by parameter;
    a lint takes `own`'s severity, a constraint only where `own` writes one."""
    if any(FAMILY[c.name] == "format" for c in own):
        template = tuple(c for c in template if FAMILY[c.name] != "format")
    merged = list(template)
    for check in own:
        same = [i for i, c in enumerate(template) if c.name == check.name and c.name not in ADDITIVE]
        for i in same:
            params = {**merged[i].params, **{k: v for k, v in check.params.items() if v is not None}}
            inherited = merged[i].severity if FAMILY[check.name] == "constraints" else "error"
            merged[i] = Check(check.name, params, check.severity or inherited)
        if not same:
            merged.append(check)
    return tuple(sorted(merged, key=lambda c: _ORDER.index(FAMILY[c.name])))
