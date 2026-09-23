"""A test file (`*.eval.yml`) read into dataclasses. Specified in specs/README.md.

Every rule about what a file may contain is enforced here, so a bad file fails at load time
with a `LoadError` and nothing downstream validates again. Check parameters are read by
`checks`, templates by `templates`, paths by `paths`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("static-check",)


class LoadError(Exception):
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

    `params` holds only what the entry wrote, after validation and normalisation by `checks`:
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

    `checks` is lint, format and constraints in that order, template entries before the
    test's own, file order within each.
    """

    id: str
    kind: str
    name: str
    prompt: PromptSpec
    needs: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()


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
    """Read one file, resolve its `uses` and paths, validate everything. Raises `LoadError`.

    A key repeated in any mapping is an error, where PyYAML would silently keep the last one.
    """
    # `checks` and `templates` import `Check` from this module: import them here, not at the top.
    # The duplicate-key check reads the node's key pairs in `construct_mapping`, before merge
    # keys are flattened.
    raise NotImplementedError
