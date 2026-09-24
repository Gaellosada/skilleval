"""A prompt as text, plus the extractors the checks share. Detection rules: specs/static-checking.md."""

from dataclasses import dataclass
from pathlib import Path


class PromptError(Exception):
    """The prompt cannot be read or parsed: missing file, undecodable bytes, unclosed frontmatter."""


@dataclass(frozen=True)
class Prompt:
    """`path` is None for an inline prompt; `root` is the test file's project root, or None."""

    text: str
    path: Path | None = None
    root: Path | None = None


@dataclass(frozen=True)
class Fence:
    """A fenced code block: the tag lowercased, `not_specified` when absent, and the line of its opening fence."""

    lang: str
    line: int


@dataclass(frozen=True)
class Link:
    """An inline markdown link or image, outside fences."""

    target: str
    line: int


@dataclass(frozen=True)
class Token:
    """Something detected in the text: a path or a URL."""

    text: str
    line: int


def read(path: Path, root: Path | None = None) -> Prompt:
    """Load a file as a prompt. Raises `PromptError` when it cannot be read (missing, a
    directory, not UTF-8) or opens a `---` frontmatter block on line 1 that never closes."""
    raise NotImplementedError


def fences(prompt: Prompt) -> list[Fence]:
    """Fenced blocks, in order. Three or more backticks or tildes open one; the closing fence is the
    same character and at least as long; an unclosed fence runs to the end."""
    raise NotImplementedError


def links(prompt: Prompt) -> list[Link]:
    """Inline `[text](target)` links and `![alt](target)` images outside fences, in order."""
    raise NotImplementedError


def headings(prompt: Prompt) -> list[str]:
    """GitHub slugs of the ATX headings outside fences, in order; duplicates get `-1`, `-2`, ..."""
    raise NotImplementedError


def paths(prompt: Prompt) -> list[Token]:
    """Path-looking tokens outside fences, stripped of surrounding quotes and trailing punctuation."""
    raise NotImplementedError


def urls(prompt: Prompt) -> list[Token]:
    """`http(s)://` URLs anywhere, fences included, trailing punctuation stripped."""
    raise NotImplementedError


def host(url: str) -> str:
    """The host of a URL: lowercased, without port or credentials."""
    raise NotImplementedError
