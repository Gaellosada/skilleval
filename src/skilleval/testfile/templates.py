"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple

from skilleval.testfile import paths
from skilleval.testfile.checks import FAMILY, read_checks
from skilleval.testfile.document import (
    kind_of,
    known_keys,
    mapping,
    root_of,
    section,
)
from skilleval.testfile.evaluation import BODY_KEYS, Body, read_body
from skilleval.testfile.schema import Check, Evaluation, at

TEMPLATE_KEYS = {
    "static-check": frozenset({"kind", "lint", "format", "constraints"}),
    "evaluation": frozenset({"kind"}) | BODY_KEYS,
}
_ORDER = ("lint", "format", "constraints")
_ADDITIVE = frozenset({"contains", "contains_any", "contains_none", "matches", "matches_any", "matches_none"})


class Template(NamedTuple):
    """A template's kind and what it holds: the checks of a static-check or the body of an
    evaluation, the other left empty."""

    kind: str
    checks: tuple[Check, ...] = ()
    evaluation: Body = Body()


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
        kind = kind_of(body, path, key)
        known_keys(body, TEMPLATE_KEYS[kind], path, key)
        if kind == "evaluation":
            templates[name] = Template(kind, evaluation=read_body(body, path=path, key=key, resolve=resolve))
        else:
            templates[name] = Template(kind, read_checks(body, path=path, key=key, resolve=resolve))
    return templates


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """A template's checks with a test's own merged in, lint then format then constraints:
    a format in `own` replaces the template's; a `contains*` or `matches*` entry is added; any other entry
    named on both sides overrides each of the template's in place, parameter by parameter;
    a lint takes `own`'s severity, a constraint only where `own` writes one."""
    if any(FAMILY[c.name] == "format" for c in own):
        template = tuple(c for c in template if FAMILY[c.name] != "format")
    merged = list(template)
    for check in own:
        same = [i for i, c in enumerate(template) if c.name == check.name and c.name not in _ADDITIVE]
        for i in same:
            written = {k: v for k, v in check.params.items() if v is not None}  # None: an unset min or max
            inherited = merged[i].severity if FAMILY[check.name] == "constraints" else None
            merged[i] = Check(check.name, {**merged[i].params, **written}, check.severity or inherited)
        if not same:
            merged.append(check)
    return tuple(sorted(merged, key=lambda c: _ORDER.index(FAMILY[c.name])))


def merge_bodies(bodies: Sequence[Body], *, path: Path, key: str) -> Evaluation:
    """The evaluation of the test written at `key`, from the bodies of its templates in `uses`
    order and its own, last.

    `model` and the limits are the last written, and `setup` likewise sub-key by sub-key.
    Each body holding a `task` adds one to the chain; an `expect` goes to its own body's task,
    or without one to the nearest task above. The expectations landing on one task join by
    what they check, their checks merged by `merge`; a file's existence takes the last
    severity written.

    Raises `LoadError` for what only shows once merged: no task, no model, no harness, both
    system prompts, an `expect` with no task above it.
    """
    raise NotImplementedError
