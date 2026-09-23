"""Test files: YAML in, validated dataclasses out. Specified in specs/README.md and specs/templates.md.

Every rule about what a file may contain lives here, including check parameters, so a
bad file fails at load time with a `SpecError` and nothing downstream validates again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("static-check", "evaluation", "benchmark")
LINT = ("chars", "markdown_links", "paths_exist")
FORMATS = ("anthropic-skill", "anthropic-claude")
CONSTRAINTS = (
    "words", "lines",
    "contains", "contains_any", "contains_none",
    "matches", "matches_any", "matches_none",
    "paths", "urls", "code",
)


class SpecError(Exception):
    """A file that cannot be used. `str(e)` reads `<path>: <key>: <message>`.

    `key` is the dotted location inside the file (`tests.skills.constraints[1].words.max`,
    or `tests` for the top level); `message` names the offending value and what to fix.
    """

    def __init__(self, path: Path, key: str, message: str) -> None:
        super().__init__(f"{path}: {key}: {message}")
        self.path, self.key, self.message = path, key, message


@dataclass(frozen=True)
class TextPrompt:
    """`prompt: {text: ...}` — an inline prompt with no file behind it."""

    text: str


@dataclass(frozen=True)
class FilePrompt:
    """`prompt: <path>` — one file, resolved, never globbed."""

    path: Path


@dataclass(frozen=True)
class GlobPrompt:
    """`prompt: {include, exclude}` — `include` globbed from `base`, matches filtered by `exclude`."""

    base: Path
    include: str
    exclude: tuple[str, ...] = ()


PromptSpec = TextPrompt | FilePrompt | GlobPrompt


@dataclass(frozen=True)
class Check:
    """One check entry, lint, format or constraint alike, with its parameters normalised.

    `params` holds only what the entry wrote, after validation and normalisation:
    - a bound (`min`/`max` on `words`, `lines`, `count`, `occurrences`) is always
      `{"min": int | None, "max": int | None}`; `occurrences: 4` becomes min 4, max 4, and
      `occurrences` on `contains`, `contains_any`, `matches`, `matches_any` defaults to
      `{"min": 1, "max": None}`;
    - `words` and `patterns` are always lists, read from the file when given as a path;
      `contains: Usage` becomes `{"words": ["Usage"], ...}`; `case_sensitive` on the
      `contains*` checks defaults to False; `patterns` are compiled with `re.MULTILINE`;
    - `except` is always a list;
    - lint and format checks have no parameters: `{}`.
    """

    name: str
    params: dict = field(default_factory=dict)
    severity: str = "error"


@dataclass(frozen=True)
class Test:
    """One entry of `tests`, templates merged in.

    `checks` is lint, format and constraints in that order, file order within each.
    `raw` keeps the keys of an `evaluation` or `benchmark` untouched; it is empty for a
    static-check, whose `prompt` is set.
    """

    id: str
    kind: str
    name: str
    needs: tuple[str, ...] = ()
    prompt: PromptSpec | None = None
    checks: tuple[Check, ...] = ()
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TestFile:
    """A loaded file. `root` is the resolved project root, None when the file declares none.

    `tests` keeps file order except that a test comes after the tests it `needs`.
    A template-only file has no tests.
    """

    path: Path
    name: str
    root: Path | None
    tests: dict[str, Test]


def load(path: Path) -> TestFile:
    """Read one file, resolve its `uses` and paths, validate everything. Raises `SpecError`."""
    raise NotImplementedError


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """The glob syntax of `exclude` on a prompt and `except` on `paths`: `*`, `?`, `[...]` stop at `/`, `**` crosses it.

    The regex matches the whole token (anchored at both ends). `**/` also matches nothing,
    so `**/fixtures/**` matches `fixtures/a.md`.
    """
    raise NotImplementedError
