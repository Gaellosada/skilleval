"""`uses`: references to templates and how they merge into a test. Specified in specs/templates.md."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple

from skilleval.testfile import paths
from skilleval.testfile.checks import FAMILY, LIST_PARAM, read_checks
from skilleval.testfile.document import entry, root_of, section
from skilleval.testfile.evaluation import (
    BODY_KEYS,
    SYSTEM_PROMPTS,
    Body,
    join,
    read_body,
    read_judge_defaults,
)
from skilleval.testfile.schema import (
    Check,
    Evaluation,
    Expectation,
    Judge,
    LoadError,
    Run,
    Setup,
    Task,
    Usage,
    at,
)

TEMPLATE_KEYS = {
    "static-check": frozenset({"kind", "lint", "format", "constraints"}),
    "evaluation": frozenset({"kind"}) | BODY_KEYS,
}
_ORDER = ("lint", "format", "constraints")


class Template(NamedTuple):
    """A template's kind and what it holds: the checks of a static-check or the body of an
    evaluation, the other left empty."""

    kind: str
    checks: tuple[Check, ...] = ()
    body: Body = Body()


def parse_reference(reference: str, resolve: paths.Resolver) -> tuple[Path, str]:
    """Split `path#name` into the template file's resolved path and the template name.
    Raises `ValueError` without a `#name`, or from `resolve`."""
    file, sep, name = reference.partition("#")
    if not (sep and name):
        raise ValueError(f"{reference!r} is not of the form path#template")
    return resolve(file), name


def read_templates(document: dict[str, Any], path: Path) -> dict[str, Template]:
    """The `templates` section of the file at `path`, read into `document`, validated and
    keyed by name, a `judge` block taking the `judge_defaults` of this file. Reads those two
    and never the file's `tests`, so a file may use its own templates. Raises `LoadError`."""
    resolve = partial(paths.resolve, file=path, root=root_of(document, path))
    judge_defaults = read_judge_defaults(document, path)
    templates = {}
    for name, value in section(document, "templates", path).items():
        key = at("templates", name)
        kind, body = entry(value, TEMPLATE_KEYS, path, key)
        templates[name] = read_own(kind, body, path=path, key=key, resolve=resolve, judge_defaults=judge_defaults)
    return templates


def read_own(
    kind: str, body: dict[str, Any], *, path: Path, key: str, resolve: paths.Resolver, judge_defaults: dict[str, Any],
) -> Template:
    """What the test or template body of `kind` written at `key` holds itself, nothing merged,
    its `judge` blocks with the `judge_defaults` of its file."""
    if kind == "evaluation":
        return Template(kind, body=read_body(body, path=path, key=key, resolve=resolve, judge_defaults=judge_defaults))
    return Template(kind, read_checks(body, path=path, key=key, resolve=resolve))


def merge(template: tuple[Check, ...], own: tuple[Check, ...]) -> tuple[Check, ...]:
    """A template's checks with a test's own merged in, lint then format then constraints:
    a format in `own` replaces the template's; a `contains*` or `matches*` entry is added; any other entry
    named on both sides overrides each of the template's in place, parameter by parameter;
    a lint takes `own`'s severity, a constraint only where `own` writes one."""
    if any(FAMILY[c.name] == "format" for c in own):
        template = tuple(c for c in template if FAMILY[c.name] != "format")
    merged = list(template)
    for check in own:
        # the checks taking a word or pattern list, contains* and matches*, are the additive ones
        same = [i for i, c in enumerate(template) if c.name == check.name and c.name not in LIST_PARAM]
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
    what they check, their checks merged by `merge`; a file's existence stays `warn` only
    when every expectation of the file says so. A `Run`, a `Judge` or a `Usage` joins none
    and keeps its place.

    Raises `LoadError` for what only shows once merged: no task, no model, no harness, both
    system prompts, an `expect` with no task above it.
    """
    if all(body.task is None for body in bodies):
        raise LoadError(path, at(key, "task"), "task is missing, here and in the templates used")
    written = {
        name: value for body in bodies for name in ("model", "max_tokens", "max_budget_usd")
        if (value := getattr(body, name)) is not None
    }
    if "model" not in written:
        raise LoadError(path, at(key, "model"), "model is missing, here and in the templates used")
    setup = {name: value for body in bodies for name, value in body.setup.items()}
    if "harness" not in setup:
        raise LoadError(path, at(at(key, "setup"), "harness"), "harness is missing, here and in the templates used")
    if all(name in setup for name in SYSTEM_PROMPTS):
        raise LoadError(path, at(key, "setup"), f"{' and '.join(SYSTEM_PROMPTS)} are exclusive, and the "
                        "setup holds both, templates included; keep one")
    chain: list[tuple[str, list[Expectation | Run | Judge | Usage]]] = []
    for used, body in enumerate(bodies, 1):
        if body.task is not None:
            chain.append((body.task, []))
        if body.expect and not chain:
            raise LoadError(path, at(key, "uses"), f"template {used} of those used holds an expect with no task "
                            "above it; give it a task, or use before it a template that holds one")
        if body.expect:
            chain[-1][1].extend(body.expect)
    return Evaluation(Setup(**setup), tasks=tuple(Task(text, join(expect, merge)) for text, expect in chain), **written)
