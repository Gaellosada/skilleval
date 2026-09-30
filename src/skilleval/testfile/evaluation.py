"""The evaluation keys of a test or a template, read as written; `templates.merge_bodies`
makes one `Evaluation` of them. Specified in specs/evaluations.md."""

import operator
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast, get_args

from skilleval.testfile.checks import (
    FAMILY,
    Invalid,
    Reader,
    boolean,
    choice,
    parse_expected,
    read_at,
    read_expected,
    severity_of,
)
from skilleval.testfile.document import known_keys, mapping, names, text_or_file
from skilleval.testfile.paths import HOME, Resolver
from skilleval.testfile.schema import (
    Answer,
    Block,
    Check,
    Effort,
    Expectation,
    Harness,
    Judge,
    LoadError,
    Run,
    Usage,
    at,
)

BODY_KEYS = frozenset({"setup", "model", "task", "expect", "max_tokens", "max_budget_usd"})
SYSTEM_PROMPTS = ("override_system_prompt", "append_system_prompt")
_FILE_KEYS = {"with_path", "severity", "format"} | {name for name, family in FAMILY.items() if family == "constraints"}


@dataclass(frozen=True)
class Body:
    """The evaluation keys one test or template wrote, validated and normalised, nothing
    merged: a key it did not write is None or empty. `setup` holds the sub-keys written, each
    under the name and with the value of its `Setup` field."""

    setup: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    task: str | None = None
    expect: tuple[Block, ...] = ()
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


def _workspace_file(value: object) -> str:
    """The path of a file of the workspace, without its detours: relative to it and inside it."""
    path = os.path.normpath(value) if isinstance(value, str) else "."
    if path == "." or str(value).startswith("./") or os.path.isabs(path) or path.split(os.sep)[0] == "..":
        raise Invalid(f"expected the path of a file relative to the workspace, not {value!r}")
    return path


def _answer(value: object) -> Answer:
    """The answer a `judge` block requires: the text YES or NO, or the boolean YAML reads of one unquoted."""
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if value not in get_args(Answer):
        raise Invalid(f"require is YES or NO, the answer that passes, not {value!r}")
    return cast(Answer, value)


_SCALARS: dict[str, Reader] = {
    "task": _text, "model": _text, "max_tokens": _positive_integer, "max_budget_usd": _positive,
}
_CHOICES: dict[str, Reader] = {
    "harness": choice(*get_args(Harness)),
    "permissions": choice("always_ask", "bypass"),
    "effort": choice(*get_args(Effort)),
}
_JUDGE: dict[str, Reader] = {  # what `judge_defaults` sets, and a `judge` block over it
    name: (_SCALARS | _CHOICES)[name] for name in ("model", "effort", "harness", "max_tokens", "max_budget_usd")
}
_SEES: dict[str, Reader] = {"can_see_task": boolean, "can_see_response": boolean}
_BESIDE: dict[str, tuple[str, ...]] = {  # the keys a block takes beside the one naming what it checks, `severity` aside
    "response": (), "file": (), "run": ("timeout",), "judge": ("require", "files", *_SEES, *_JUDGE), "usage": (),
}
_BOUNDS: dict[str, Reader] = {"max_seconds": _positive, "max_output_tokens": _positive_integer}  # what `usage` holds


def _written(body: dict[str, Any], readers: dict[str, Reader], path: Path, key: str) -> dict[str, Any]:
    """The keys of `readers` that the mapping `body`, written at `key`, holds, each read by its reader."""
    return {name: read_at(read, body[name], path, at(key, name)) for name, read in readers.items() if name in body}


def read_body(body: dict[str, Any], *, path: Path, key: str, resolve: Resolver, judge_defaults: dict[str, Any]) -> Body:
    """The evaluation keys of the test or template body written at `key`: `setup` through
    `read_setup`, `expect` through `read_expect`, `task` and `model` strings that are not
    blank, `max_tokens` a positive integer and `max_budget_usd` a positive number. Raises
    `LoadError` at the key of the offending value."""
    written = _written(body, _SCALARS, path, key)
    if "setup" in body:
        written["setup"] = read_setup(body["setup"], path=path, key=at(key, "setup"), resolve=resolve)
    if "expect" in body:
        written["expect"] = read_expect(
            body["expect"], path=path, key=at(key, "expect"), resolve=resolve, judge_defaults=judge_defaults,
        )
    return Body(**written)


def read_judge_defaults(document: dict[str, Any], path: Path) -> dict[str, Any]:
    """The `judge_defaults` of the file at `path`, read into `document`: what it sets of the
    judge of the file's `judge` blocks, each key under the name of its `Judge` field, and
    nothing when the file has no such section. Raises `LoadError`."""
    if "judge_defaults" not in document:
        return {}
    written = mapping(document["judge_defaults"], path, "judge_defaults")
    known_keys(written, _JUDGE, path, "judge_defaults")
    return _written(written, _JUDGE, path, "judge_defaults")


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
    setup = _written(written, _CHOICES, path, key)
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


def read_expect(
    value: object, *, path: Path, key: str, resolve: Resolver, judge_defaults: dict[str, Any],
) -> tuple[Block, ...]:
    """The `expect` list written at `key`, one `Expectation` per thing checked, in order of
    first appearance: every `response` block joins into one, as do the `file` blocks of the
    same `with_path`, their checks in file order. Each `run` block is a `Run` of its own, in
    its place, each `judge` block a `Judge`, as `_judge` reads it over `judge_defaults`, and
    each `usage` block a `Usage`.

    A block is a mapping holding `response`, `file`, `run`, `judge` or `usage`. `response` is a list of
    constraint and format entries, read by `checks.read_expected`, with `severity` beside it.
    `file` holds `with_path`, `severity`, and `format` and constraint names as keys, each read
    by `checks.parse_expected` as the entry `{name: parameters}`. A check that writes no severity
    takes that of its own block; a file's existence is `warn` when every block of the file
    says so, else None. `with_path` stays inside the workspace: `./`, an absolute path and
    one climbing out with `..` are errors. `run` is a command that is not blank, with
    `timeout`, a positive number, and `severity` beside it; its directory is that of `path`,
    made absolute, since the command runs elsewhere. `usage` holds `max_seconds`, a positive
    number, `max_output_tokens`, a positive integer, or both, with `severity` beside it.
    Raises `LoadError`.
    """
    if not isinstance(value, list):
        raise LoadError(path, key, f"expect is a list of blocks, not {value!r}")
    blocks = (
        _block(block, path=path, key=at(key, i), resolve=resolve, judge_defaults=judge_defaults)
        for i, block in enumerate(value)
    )
    return join(blocks, operator.add)


def _block(
    value: object, *, path: Path, key: str, resolve: Resolver, judge_defaults: dict[str, Any],
) -> Block:
    """One block of `expect`, each check at its own severity or else the block's."""
    block = mapping(value, path, key)
    named = [name for name in _BESIDE if name in block]
    known_keys(block, {*_BESIDE, "severity", *(k for name in named for k in _BESIDE[name])}, path, key)
    if len(named) != 1:
        raise LoadError(path, key, f"a block holds response, file, run, judge or usage, one of them, not {block!r}")
    if "judge" in block:
        return _judge(block, path, key, judge_defaults)
    if "usage" in block:
        k = at(key, "usage")
        bounds = mapping(block["usage"], path, k)
        known_keys(bounds, _BOUNDS, path, k)
        if not bounds:
            raise LoadError(path, k, f"usage holds max_seconds, max_output_tokens or both, not {bounds!r}")
        return Usage(**_written(bounds, _BOUNDS, path, k), severity=read_at(severity_of, block, path, key))
    if "run" in block:
        timeout = read_at(_positive, block.get("timeout", Run.timeout), path, at(key, "timeout"))
        severity = read_at(severity_of, block, path, key)
        return Run(read_at(_text, block["run"], path, at(key, "run")), path.absolute().parent, timeout, severity)
    if "response" in block:
        section, with_path = block, None
        checks = read_expected(block["response"], path=path, key=at(key, "response"), resolve=resolve)
    else:
        if "severity" in block:
            raise LoadError(path, at(key, "severity"), "the severity of a file block sits in file, beside with_path")
        key = at(key, "file")
        section = mapping(block["file"], path, key)
        known_keys(section, _FILE_KEYS, path, key)
        if "with_path" not in section:
            raise LoadError(path, at(key, "with_path"), "with_path is required, the path of a file relative to the workspace")
        with_path = read_at(_workspace_file, section["with_path"], path, at(key, "with_path"))
        checks = tuple(
            parse_expected({name: params}, path=path, key=key, resolve=resolve)
            for name, params in section.items() if name not in ("with_path", "severity")
        )
    severity = read_at(severity_of, section, path, key)
    checks = tuple(replace(check, severity=check.severity or severity) for check in checks)
    return Expectation(with_path, checks, "warn" if with_path is not None and severity == "warn" else None)


def _judge(block: dict[str, Any], path: Path, key: str, judge_defaults: dict[str, Any]) -> Judge:
    """The `judge` block written at `key`: a question that is not blank, `require`, the
    answer that passes, `files`, one path or a list, each a file of the workspace, the two
    `can_see_` booleans, `severity`, and the keys of `_JUDGE`, those it does not write being
    those of `judge_defaults`."""
    if "require" not in block:
        raise LoadError(path, at(key, "require"), "require is required, YES or NO, the answer that passes")
    files = names(block.get("files", []), path, at(key, "files"))
    return Judge(
        read_at(_text, block["judge"], path, at(key, "judge")),
        read_at(_answer, block["require"], path, at(key, "require")),
        tuple(read_at(_workspace_file, file, path, k) for file, k in files),
        severity=read_at(severity_of, block, path, key),
        **judge_defaults | _written(block, _SEES | _JUDGE, path, key),
    )


def join(
    expectations: Iterable[Block],
    combine: Callable[[tuple[Check, ...], tuple[Check, ...]], tuple[Check, ...]],
) -> tuple[Block, ...]:
    """One expectation per thing checked, in order of first appearance. Those on the same
    thing have their checks combined by `combine`, the earlier ones first, and a file's
    existence stays `warn` only when every one of them says so. A `Run`, a `Judge` or a
    `Usage` joins none, an equal one included, and keeps its place."""
    joined: dict[object, Block] = {}
    for new in expectations:
        if not isinstance(new, Expectation):
            joined[object()] = new  # a key no other is equal to
            continue
        if isinstance(old := joined.get(new.with_path), Expectation):
            new = Expectation(new.with_path, combine(old.checks, new.checks), old.severity and new.severity)
        joined[new.with_path] = new
    return tuple(joined.values())
