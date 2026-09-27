"""A test file (`*.eval.yml`) read into dataclasses. Specified in specs/README.md.

Every rule about what a file may contain is enforced here, so a bad file fails at load time
with a `LoadError` and nothing downstream validates again. `schema` holds the dataclasses,
`document` reads the YAML, `checks` reads check entries, `evaluation` reads the keys of an
evaluation, `templates` reads `uses`, `paths` resolves paths.
"""

from functools import partial, reduce
from pathlib import Path
from typing import Any

from skilleval.testfile import paths
from skilleval.testfile.checks import Invalid, globs, read_checks, strings
from skilleval.testfile.document import (
    kind_of,
    known_keys,
    mapping,
    read_document,
    root_of,
    section,
    text_or_file,
)
from skilleval.testfile.evaluation import read_body
from skilleval.testfile.schema import (
    Check,
    Evaluation,
    Expectation,
    FilePrompt,
    GlobPrompt,
    LoadError,
    PromptSpec,
    Setup,
    Task,
    Test,
    TestFile,
    TextPrompt,
    at,
)
from skilleval.testfile.templates import (
    TEMPLATE_KEYS,
    Template,
    merge,
    merge_bodies,
    parse_reference,
    read_templates,
)

__all__ = [
    "Check", "Evaluation", "Expectation", "FilePrompt", "GlobPrompt", "LoadError", "PromptSpec",
    "Setup", "Task", "Test", "TestFile", "TextPrompt", "load",
]

TEST_KEYS = {  # what a test adds to the keys of a template of its kind
    "static-check": frozenset({"prompt", "needs", "uses"}),
    "evaluation": frozenset({"needs", "uses"}),
}
Templates = dict[Path, dict[str, Template]]


def load(path: Path) -> TestFile:
    """Read one file, resolve its `uses` and paths, validate everything. Raises `LoadError`."""
    document = read_document(path)
    known_keys(document, {"root", "tests", "templates"}, path, "")
    if "tests" not in document and "templates" not in document:
        raise LoadError(path, "tests",
                        "a file declares tests, templates or both; this one has neither")
    root = root_of(document, path)
    templates = {path: read_templates(document, path)}
    resolve = partial(paths.resolve, file=path, root=root)
    tests, need_keys = {}, {}
    for test_id, body in section(document, "tests", path).items():
        key = at("tests", test_id)
        body = mapping(body, path, key)
        kind = kind_of(body, path, key)
        known_keys(body, TEMPLATE_KEYS[kind] | TEST_KEYS[kind], path, key)
        need_keys[test_id] = _names(body.get("needs", []), path, at(key, "needs"))
        needs = tuple(need for need, _ in need_keys[test_id])
        used = _uses(body.get("uses", []), kind, path, at(key, "uses"), resolve, templates)
        if kind == "evaluation":
            bodies = [*(t.evaluation for t in used), read_body(body, path=path, key=key, resolve=resolve)]
            tests[test_id] = Test(test_id, kind, needs=needs, evaluation=merge_bodies(bodies, path=path, key=key))
        else:
            checks = [*(t.checks for t in used), read_checks(body, path=path, key=key, resolve=resolve)]
            prompt = _prompt(body, path, key, root, resolve)
            tests[test_id] = Test(test_id, kind, prompt, needs, reduce(merge, checks, ()))
    _known_needs(need_keys, path)
    return TestFile(path, root, {test_id: tests[test_id] for test_id in _order(tests, path)})


def _known_needs(need_keys: dict[str, list[tuple[str, str]]], path: Path) -> None:
    """Every need, given with its key under the id of its test, names another test of the file."""
    for test_id, needs in need_keys.items():
        for need, key in needs:
            if need == test_id or need not in need_keys:
                what = "the test itself" if need == test_id else "not a test of this file"
                raise LoadError(path, key, f"{need!r} is {what}")


def _names(value: object, path: Path, key: str) -> list[tuple[str, str]]:
    """A name or a list of names, each with its dotted key: the one name at `key`, list
    entries at `key[i]`."""
    try:
        names = strings(value)
    except ValueError as e:
        raise LoadError(path, key, str(e)) from e
    return [(name, key if isinstance(value, str) else at(key, i)) for i, name in enumerate(names)]


def _uses(
    value: object, kind: str, path: Path, key: str, resolve: paths.Resolver, templates: Templates,
) -> list[Template]:
    """The templates `value` references, each of the test's `kind`. `templates` holds every
    file read so far in this load, by path; a file not in it is read and added."""
    used = []
    for reference, k in _names(value, path, key):
        try:
            file, name = parse_reference(reference, resolve)
        except ValueError as e:
            raise LoadError(path, k, str(e)) from e
        if not file.is_file():
            raise LoadError(path, k, f"{file} is not a file")
        if file not in templates:
            templates[file] = read_templates(read_document(file), file)
        available = templates[file]
        if name not in available:
            has = ", ".join(available) or "none"
            raise LoadError(path, k, f"{file} defines no template {name!r}; it has {has}")
        if available[name].kind != kind:
            raise LoadError(path, k, f"template {name!r} is of kind {available[name].kind}; use one of kind {kind}")
        used.append(available[name])
    return used


def _prompt(
    body: dict[str, Any], path: Path, key: str, root: Path | None, resolve: paths.Resolver,
) -> PromptSpec:
    key, value = at(key, "prompt"), body.get("prompt")
    if isinstance(value, dict):
        known_keys(value, {"file", "include", "exclude"}, path, key)
        if "include" in value and "file" not in value:
            return _glob(value, path, key, root)
    prompt = text_or_file(value, path, key, resolve)
    if prompt is None:
        forms = "the prompt itself, {file: ...} or {include: ..., exclude: ...}"
        raise LoadError(path, key, f"a prompt is {forms}, not {value!r}")
    return prompt


def _glob(value: dict[str, Any], path: Path, key: str, root: Path | None) -> GlobPrompt:
    include = value["include"]
    pattern = include.removeprefix("./") if isinstance(include, str) else ""
    if not pattern or Path(pattern).is_absolute():
        raise LoadError(path, at(key, "include"), "include is one glob, relative to the file "
                        f"when it starts with ./ and to the root otherwise, not {include!r}")
    try:
        base = paths.base(include, path, root)
    except ValueError as e:
        raise LoadError(path, at(key, "include"), str(e)) from e
    try:
        exclude = globs(value.get("exclude", []))
    except Invalid as e:
        raise LoadError(path, reduce(at, e.parts, at(key, "exclude")), str(e)) from e
    return GlobPrompt(base, pattern, tuple(exclude))


def _order(tests: dict[str, Test], path: Path) -> list[str]:
    """File order, except that a needed test comes just before the first test needing it."""
    done: list[str] = []
    active: set[str] = set()

    def visit(test_id: str) -> None:
        if test_id in done:
            return
        if test_id in active:
            key = at(at("tests", test_id), "needs")
            raise LoadError(path, key, f"needs form a cycle through {test_id!r}")
        active.add(test_id)
        for need in tests[test_id].needs:
            visit(need)
        active.remove(test_id)
        done.append(test_id)

    for test_id in tests:
        visit(test_id)
    return done
