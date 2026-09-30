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
from skilleval.testfile.checks import globs, read_at
from skilleval.testfile.document import (
    entry,
    known_keys,
    names,
    read_document,
    root_of,
    section,
    text_or_file,
)
from skilleval.testfile.evaluation import read_judge_defaults
from skilleval.testfile.schema import (
    Check,
    Effort,
    Evaluation,
    Expectation,
    FilePrompt,
    GlobPrompt,
    Judge,
    LoadError,
    PromptSpec,
    Run,
    Setup,
    Task,
    Test,
    TestFile,
    TextPrompt,
    Usage,
    at,
)
from skilleval.testfile.templates import (
    TEMPLATE_KEYS,
    Template,
    merge,
    merge_bodies,
    parse_reference,
    read_own,
    read_templates,
)

__all__ = [
    "Check", "Effort", "Evaluation", "Expectation", "FilePrompt", "GlobPrompt", "Judge", "LoadError",
    "PromptSpec", "Run", "Setup", "Task", "Test", "TestFile", "TextPrompt", "Usage", "load",
]

TEST_KEYS = {  # a template's keys, plus what a test adds
    "static-check": TEMPLATE_KEYS["static-check"] | {"prompt", "needs", "uses"},
    "evaluation": TEMPLATE_KEYS["evaluation"] | {"needs", "uses"},
}
Templates = dict[Path, dict[str, Template]]


def load(path: Path) -> TestFile:
    """Read one file, resolve its `uses` and paths, validate everything. Raises `LoadError`."""
    document = read_document(path)
    known_keys(document, {"root", "judge_defaults", "tests", "templates"}, path, "")
    if "tests" not in document and "templates" not in document:
        raise LoadError(path, "tests",
                        "a file declares tests, templates or both; this one has neither")
    root = root_of(document, path)
    templates = {path: read_templates(document, path)}
    resolve = partial(paths.resolve, file=path, root=root)
    judge_defaults = read_judge_defaults(document, path)
    tests, need_keys = {}, {}
    for test_id, value in section(document, "tests", path).items():
        key = at("tests", test_id)
        kind, body = entry(value, TEST_KEYS, path, key)
        need_keys[test_id] = names(body.get("needs", []), path, at(key, "needs"))
        needs = tuple(need for need, _ in need_keys[test_id])
        used = _uses(body.get("uses", []), kind, path, at(key, "uses"), resolve, templates)
        used.append(read_own(kind, body, path=path, key=key, resolve=resolve, judge_defaults=judge_defaults))
        if kind == "evaluation":
            evaluation = merge_bodies([t.body for t in used], path=path, key=key)
            tests[test_id] = Test(test_id, kind, needs=needs, evaluation=evaluation)
        else:
            prompt = _prompt(body, path, key, root, resolve)
            tests[test_id] = Test(test_id, kind, prompt, needs, reduce(merge, [t.checks for t in used], ()))
    return TestFile(path, root, {test_id: tests[test_id] for test_id in _order(need_keys, path)})


def _uses(
    value: object, kind: str, path: Path, key: str, resolve: paths.Resolver, templates: Templates,
) -> list[Template]:
    """The templates `value` references, each of the test's `kind`. `templates` holds every
    file read so far in this load, by path; a file not in it is read and added."""
    used = []
    for reference, k in names(value, path, key):
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
    exclude = read_at(globs, value.get("exclude", []), path, at(key, "exclude"))
    return GlobPrompt(base, pattern, tuple(exclude))


def _order(need_keys: dict[str, list[tuple[str, str]]], path: Path) -> list[str]:
    """File order, except that a needed test comes just before the first test needing it.
    `need_keys` holds each test's needs, each with its key. Raises `LoadError` at a need that
    is the test itself or not a test of the file, or at a test whose needs close a cycle."""
    done: list[str] = []
    active: set[str] = set()

    def visit(test_id: str) -> None:
        if test_id in done:
            return
        if test_id in active:
            raise LoadError(path, at(at("tests", test_id), "needs"), f"needs form a cycle through {test_id!r}")
        active.add(test_id)
        for need, key in need_keys[test_id]:
            if need == test_id or need not in need_keys:
                what = "the test itself" if need == test_id else "not a test of this file"
                raise LoadError(path, key, f"{need!r} is {what}")
            visit(need)
        active.remove(test_id)
        done.append(test_id)

    for test_id in need_keys:
        visit(test_id)
    return done
