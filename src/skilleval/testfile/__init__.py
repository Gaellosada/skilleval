"""A test file (`*.eval.yml`) read into dataclasses. Specified in specs/README.md.

Every rule about what a file may contain is enforced here, so a bad file fails at load time
with a `LoadError` and nothing downstream validates again. `schema` holds the dataclasses,
`document` reads the YAML, `checks` reads check entries, `templates` reads `uses`, `paths`
resolves paths.
"""

from functools import partial, reduce
from pathlib import Path
from typing import Any

from skilleval.testfile import paths
from skilleval.testfile.checks import read_checks
from skilleval.testfile.document import (
    KINDS,
    kind_of,
    known_keys,
    mapping,
    read_document,
    root_of,
)
from skilleval.testfile.schema import (
    Check,
    FilePrompt,
    GlobPrompt,
    LoadError,
    PromptSpec,
    Test,
    TestFile,
    TextPrompt,
    at,
)
from skilleval.testfile.templates import merge, parse_reference, read_templates

__all__ = [
    "Check", "FilePrompt", "GlobPrompt", "KINDS", "LoadError", "PromptSpec", "Test", "TestFile",
    "TextPrompt", "load",
]

TEST_KEYS = frozenset({"kind", "prompt", "needs", "uses", "lint", "format", "constraints"})


def load(path: Path) -> TestFile:
    """Read one file, resolve its `uses` and paths, validate everything. Raises `LoadError`."""
    document = read_document(path)
    known_keys(document, {"root", "tests", "templates"}, path, "")
    if "tests" not in document and "templates" not in document:
        raise LoadError(path, "tests",
                        "a file declares tests, templates or both; this one has neither")
    root = root_of(document, path)
    read_templates(path)
    resolve = partial(paths.resolve, file=path, root=root)
    tests, need_keys = {}, {}
    for test_id, body in mapping(document.get("tests", {}), path, "tests").items():
        key = at("tests", test_id)
        body = mapping(body, path, key)
        known_keys(body, TEST_KEYS, path, key)
        needs = _names(body.get("needs", []), path, at(key, "needs"))
        checks = [*_uses(body.get("uses", []), path, at(key, "uses"), resolve),
                  read_checks(body, path=path, key=key, resolve=resolve)]
        tests[test_id] = Test(test_id, kind_of(body, path, key),
                              _prompt(body, path, key, root, resolve),
                              tuple(need for need, _ in needs), reduce(merge, checks, ()))
        need_keys[test_id] = needs
    for test_id, needs in need_keys.items():
        for need, key in needs:
            if need == test_id or need not in tests:
                what = "the test itself" if need == test_id else "not a test of this file"
                raise LoadError(path, key, f"{need!r} is {what}")
    return TestFile(path, root, {test_id: tests[test_id] for test_id in _order(tests, path)})


def _names(value: object, path: Path, key: str) -> list[tuple[str, str]]:
    """A name or a list of names, each with its dotted key: the one name at `key`, list
    entries at `key[i]`."""
    if isinstance(value, str):
        return [(value, key)]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [(v, at(key, i)) for i, v in enumerate(value)]
    raise LoadError(path, key, f"expected a name or a list of names, not {value!r}")


def _uses(value: object, path: Path, key: str, resolve: paths.Resolver) -> list[tuple[Check, ...]]:
    templates = []
    for reference, k in _names(value, path, key):
        try:
            file, name = parse_reference(reference, resolve)
        except ValueError as e:
            raise LoadError(path, k, str(e)) from e
        if not file.is_file():
            raise LoadError(path, k, f"{file} is not a file")
        available = read_templates(file)
        if name not in available:
            has = ", ".join(available) or "none"
            raise LoadError(path, k, f"{file} defines no template {name!r}; it has {has}")
        templates.append(available[name])
    return templates


def _prompt(
    body: dict[str, Any], path: Path, key: str, root: Path | None, resolve: paths.Resolver,
) -> PromptSpec:
    key, value = at(key, "prompt"), body.get("prompt")
    if isinstance(value, str):
        try:
            return FilePrompt(resolve(value))
        except ValueError as e:
            raise LoadError(path, key, str(e)) from e
    if isinstance(value, dict):
        known_keys(value, {"text", "include", "exclude"}, path, key)
        if set(value) == {"text"} and isinstance(value["text"], str):
            return TextPrompt(value["text"])
        if "include" in value and "text" not in value:
            return _glob(value, path, key, root)
    forms = "a path, {text: ...} or {include: ..., exclude: ...}"
    raise LoadError(path, key, f"a prompt is {forms}, not {value!r}")


def _glob(value: dict[str, Any], path: Path, key: str, root: Path | None) -> GlobPrompt:
    include = value["include"]
    if not isinstance(include, str):
        raise LoadError(path, at(key, "include"), f"include is one glob, not {include!r}")
    if include.startswith("./"):
        base, include = path.parent, include[2:]
    elif root is None:
        raise LoadError(path, at(key, "include"),
                        f"{include} is relative to the project root, and the file declares no root")
    else:
        base = root
    exclude = _names(value.get("exclude", []), path, at(key, "exclude"))
    return GlobPrompt(base, include, tuple(glob for glob, _ in exclude))


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
