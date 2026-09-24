"""The shape of a loaded test file. Specified in specs/README.md."""

from dataclasses import dataclass
from pathlib import Path

from skilleval.testfile.checks import Check


class LoadError(Exception):
    """A file that cannot be used. `str(e)` reads `<path>: <key>: <message>`, or
    `<path>: <message>` when the error is the whole file (unreadable, not a mapping).

    `key` is the dotted location inside the file (`tests.skills.constraints[1].words.max`,
    `tests.skills.kind`, `templates.house_style`), empty for the whole file; `message` names
    the offending value and what to fix.
    """

    def __init__(self, path: Path, key: str, message: str) -> None:
        super().__init__(f"{path}: {key}: {message}" if key else f"{path}: {message}")
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
    """`prompt: {include, exclude}` — `include` globbed from `base` with `Path.glob` semantics
    (`**` crosses dot-directories); each match's path relative to `base` is filtered by the
    `exclude` globs of `paths.glob_to_regex`."""

    base: Path
    include: str
    exclude: tuple[str, ...] = ()


PromptSpec = TextPrompt | FilePrompt | GlobPrompt


@dataclass(frozen=True)
class Test:
    """One entry of `tests`, templates merged in.

    `checks` is lint, format and constraints in that order, template entries before the
    test's own, file order within each.
    """

    id: str
    kind: str
    prompt: PromptSpec
    needs: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()


@dataclass(frozen=True)
class TestFile:
    """A loaded file. `root` is the resolved project root, None when the file declares none.

    `tests` keeps file order except that a needed test is pulled up to just before the first
    test that needs it. A template-only file has no tests.
    """

    path: Path
    root: Path | None
    tests: dict[str, Test]
