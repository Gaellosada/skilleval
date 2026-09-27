"""The evaluation keys of a test or a template, read as written; `templates.merge_bodies`
makes one `Evaluation` of them. Specified in specs/evaluations.md."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skilleval.testfile.paths import Resolver
from skilleval.testfile.schema import Expectation

BODY_KEYS = frozenset({"setup", "model", "task", "expect", "max_tokens", "max_budget_usd"})


@dataclass(frozen=True)
class Body:
    """The evaluation keys one test or template wrote, validated and normalised, nothing
    merged: a key it did not write is None or empty. `setup` holds the sub-keys written, each
    under the name and with the value of its `Setup` field."""

    setup: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    task: str | None = None
    expect: tuple[Expectation, ...] = ()
    max_tokens: int | None = None
    max_budget_usd: float | None = None


def read_body(body: dict[str, Any], *, path: Path, key: str, resolve: Resolver) -> Body:
    """The evaluation keys of the test or template body written at `key`: `setup` through
    `read_setup`, `expect` through `read_expect`, `task` and `model` strings, `max_tokens` a
    positive integer and `max_budget_usd` a positive number. Raises `LoadError` at the key of
    the offending value."""
    raise NotImplementedError


def read_setup(value: object, *, path: Path, key: str, resolve: Resolver) -> dict[str, Any]:
    """The sub-keys of the `setup` written at `key`, for `Body.setup`.

    `harness` is `user_local`; `none` is an error saying it is not supported yet.
    `permissions` is `always_ask` or `bypass`. A system prompt is read by
    `document.text_or_file`, so the `include` form is an error. `skills` is one path or a
    list, kept as a tuple, each a directory holding a `SKILL.md`; `working_folder` is a
    directory. Paths go through `resolve`. What a setup must hold once merged is checked by
    `templates.merge_bodies`. Raises `LoadError`.
    """
    raise NotImplementedError


def read_expect(value: object, *, path: Path, key: str, resolve: Resolver) -> tuple[Expectation, ...]:
    """The `expect` list written at `key`, one `Expectation` per thing checked, in order of
    first appearance: every `response` block joins into one, as do the `file` blocks of the
    same `with_path`, their checks in file order.

    A block is a mapping holding `response` or `file`. `response` is a list of constraint
    entries, read by `checks.read_constraints`, with `severity` beside it. `file` holds
    `with_path`, `severity` and constraint names as keys, each read by `checks.parse_check`
    as the entry `{name: parameters}`. A check that writes no severity takes that of its own
    block; a file's existence is `warn` when every block of the file says so, otherwise
    `error` when one of them writes it, else None.
    `with_path` stays inside the workspace: `./`, an absolute path and one climbing out with
    `..` are errors. Raises `LoadError`.
    """
    raise NotImplementedError
