"""The evaluation keys of a test or a template, read as written; `templates.merge_bodies`
makes one `Evaluation` of them. Specified in specs/evaluations.md."""

import operator
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, get_args

from skilleval.testfile.checks import (
    FAMILY,
    Invalid,
    Reader,
    choice,
    parse_check,
    read_at,
    read_constraints,
    severity_of,
)
from skilleval.testfile.document import known_keys, mapping, names, text_or_file
from skilleval.testfile.paths import HOME, Resolver
from skilleval.testfile.schema import Check, Effort, Expectation, LoadError, Run, at

BODY_KEYS = frozenset({"setup", "model", "task", "expect", "max_tokens", "max_budget_usd"})
SYSTEM_PROMPTS = ("override_system_prompt", "append_system_prompt")
_FILE_KEYS = {"with_path", "severity"} | {name for name, family in FAMILY.items() if family == "constraints"}


@dataclass(frozen=True)
class Body:
    """The evaluation keys one test or template wrote, validated and normalised, nothing
    merged: a key it did not write is None or empty. `setup` holds the sub-keys written, each
    under the name and with the value of its `Setup` field."""

    setup: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    task: str | None = None
    expect: tuple[Expectation | Run, ...] = ()
    max_tokens: int | None = None
    max_budget_usd: float | None = None


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"expected text that is not blank, not {value!r}")
    return value


def _positive(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= sys.float_info.max:
        raise Invalid(f"expected a positive number, not {value!r}")
    return value


def _positive_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Invalid(f"expected a positive integer, not {value!r}")
    return value


def _with_path(value: object) -> str:
    path = os.path.normpath(value) if isinstance(value, str) else "."
    if path == "." or str(value).startswith("./") or os.path.isabs(path) or path.split(os.sep)[0] == "..":
        raise Invalid(f"with_path is required, the path of a file relative to the workspace, not {value!r}")
    return path


_SCALARS: dict[str, Reader] = {
    "task": _text, "model": _text, "max_tokens": _positive_integer, "max_budget_usd": _positive,
}
_CHOICES: dict[str, Reader] = {
    "harness": choice("user_local", "blank"),
    "permissions": choice("always_ask", "bypass"),
    "effort": choice(*get_args(Effort)),
}


def read_body(body: dict[str, Any], *, path: Path, key: str, resolve: Resolver) -> Body:
    """The evaluation keys of the test or template body written at `key`: `setup` through
    `read_setup`, `expect` through `read_expect`, `task` and `model` strings that are not
    blank, `max_tokens` a positive integer and `max_budget_usd` a positive number. Raises
    `LoadError` at the key of the offending value."""
    written = {name: read_at(read, body[name], path, at(key, name)) for name, read in _SCALARS.items() if name in body}
    if "setup" in body:
        written["setup"] = read_setup(body["setup"], path=path, key=at(key, "setup"), resolve=resolve)
    if "expect" in body:
        written["expect"] = read_expect(body["expect"], path=path, key=at(key, "expect"), resolve=resolve)
    return Body(**written)


def read_setup(value: object, *, path: Path, key: str, resolve: Resolver) -> dict[str, Any]:
    """The sub-keys of the `setup` written at `key`, for `Body.setup`.

    `harness` is `user_local` or `blank`, `permissions` is `always_ask` or `bypass`, `effort`
    one of the levels of `Effort`. A system prompt is read by `document.text_or_file`, so the
    `include` form is an error. `skills` is one path or a list, kept as a tuple, each a
    directory holding a `SKILL.md`; `working_folder` is a directory; neither names a
    `.skilleval` folder. Paths go through `resolve`. What a setup must hold once merged is
    checked by `templates.merge_bodies`. Raises `LoadError`.
    """
    written = mapping(value, path, key)
    known_keys(written, {*_CHOICES, *SYSTEM_PROMPTS, "skills", "working_folder"}, path, key)
    setup = {name: read_at(read, written[name], path, at(key, name)) for name, read in _CHOICES.items() if name in written}
    for name in SYSTEM_PROMPTS:
        if name in written:
            setup[name] = text_or_file(written[name], path, at(key, name), resolve)
            if setup[name] is None:
                raise LoadError(path, at(key, name),
                                f"a system prompt is the prompt itself or {{file: ...}}, not {written[name]!r}")
    if "skills" in written:
        skills = names(written["skills"], path, at(key, "skills"))
        setup["skills"] = tuple(_directory(skill, path, k, resolve, holding="SKILL.md") for skill, k in skills)
    if "working_folder" in written:
        k = at(key, "working_folder")
        setup["working_folder"] = _directory(written["working_folder"], path, k, resolve)
        if path.is_relative_to(setup["working_folder"]):
            raise LoadError(path, k, f"{written['working_folder']} holds this file, which the model would "
                            "then read in its workspace; name a folder that holds no test file")
    return setup


def _directory(written: object, path: Path, key: str, resolve: Resolver, holding: str = "") -> Path:
    """The directory written at `key`, resolved, which holds the file `holding` when one is
    named. Its path, as written, names no `HOME`, whose files are never the model's to read:
    a project that itself lives below a folder of that name is no concern of this."""
    if not isinstance(written, str) or not written:
        raise LoadError(path, key, f"expected the path of a directory, not {written!r}")
    try:
        directory = resolve(written)
    except ValueError as e:
        raise LoadError(path, key, str(e)) from e
    if not directory.is_dir():
        raise LoadError(path, key, f"{written} is not a directory")
    if holding and not (directory / holding).is_file():
        raise LoadError(path, key, f"{written} holds no {holding}")
    if HOME in Path(os.path.normpath(written)).parts:
        raise LoadError(path, key, f"{written} is in a {HOME} folder, which is skilleval's own; name a folder outside it")
    return directory


def read_expect(value: object, *, path: Path, key: str, resolve: Resolver) -> tuple[Expectation | Run, ...]:
    """The `expect` list written at `key`, one `Expectation` per thing checked, in order of
    first appearance: every `response` block joins into one, as do the `file` blocks of the
    same `with_path`, their checks in file order. Each `run` block is a `Run` of its own, in
    its place.

    A block is a mapping holding `response`, `file` or `run`. `response` is a list of
    constraint entries, read by `checks.read_constraints`, with `severity` beside it. `file`
    holds `with_path`, `severity` and constraint names as keys, each read by
    `checks.parse_check` as the entry `{name: parameters}`. A check that writes no severity
    takes that of its own block; a file's existence is `warn` when every block of the file
    says so, else None. `with_path` stays inside the workspace: `./`, an absolute path and
    one climbing out with `..` are errors. `run` is a command that is not blank, with
    `timeout`, a positive number, and `severity` beside it; its directory is that of `path`,
    made absolute, since the command runs elsewhere. Raises `LoadError`.
    """
    if not isinstance(value, list):
        raise LoadError(path, key, f"expect is a list of blocks, not {value!r}")
    blocks = (_block(block, path=path, key=at(key, i), resolve=resolve) for i, block in enumerate(value))
    return join(blocks, operator.add)


def _block(value: object, *, path: Path, key: str, resolve: Resolver) -> Expectation | Run:
    """One block of `expect`, each check at its own severity or else the block's."""
    block = mapping(value, path, key)
    beside = {"severity", "timeout"} if "run" in block else {"severity"}
    known_keys(block, {"response", "file", "run", *beside}, path, key)
    if sum(name in block for name in ("response", "file", "run")) != 1:
        raise LoadError(path, key, f"a block holds response, file or run, one of them, not {block!r}")
    if "run" in block:
        timeout = read_at(_positive, block.get("timeout", Run.timeout), path, at(key, "timeout"))
        severity = read_at(severity_of, block, path, key)
        return Run(read_at(_text, block["run"], path, at(key, "run")), path.absolute().parent, timeout, severity)
    if "response" in block:
        section, with_path = block, None
        checks = read_constraints(block["response"], path=path, key=at(key, "response"), resolve=resolve)
    else:
        if "severity" in block:
            raise LoadError(path, at(key, "severity"), "the severity of a file block sits in file, beside with_path")
        key = at(key, "file")
        section = mapping(block["file"], path, key)
        known_keys(section, _FILE_KEYS, path, key)
        with_path = read_at(_with_path, section.get("with_path"), path, at(key, "with_path"))
        checks = tuple(
            parse_check("constraints", {name: params}, path=path, key=key, resolve=resolve)
            for name, params in section.items() if name in FAMILY
        )
    severity = read_at(severity_of, section, path, key)
    checks = tuple(replace(check, severity=check.severity or severity) for check in checks)
    return Expectation(with_path, checks, "warn" if with_path is not None and severity == "warn" else None)


def join(
    expectations: Iterable[Expectation | Run],
    combine: Callable[[tuple[Check, ...], tuple[Check, ...]], tuple[Check, ...]],
) -> tuple[Expectation | Run, ...]:
    """One expectation per thing checked, in order of first appearance. Those on the same
    thing have their checks combined by `combine`, the earlier ones first, and a file's
    existence stays `warn` only when every one of them says so. A `Run` joins none, an
    equal one included, and keeps its place."""
    joined: dict[object, Expectation | Run] = {}
    for new in expectations:
        if isinstance(new, Run):
            joined[object()] = new  # a key no other is equal to
            continue
        if isinstance(old := joined.get(new.with_path), Expectation):
            new = Expectation(new.with_path, combine(old.checks, new.checks), old.severity and new.severity)
        joined[new.with_path] = new
    return tuple(joined.values())
