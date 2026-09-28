"""A prompt as text, plus the extractors the checks share. Detection rules: specs/static-checking.md."""

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


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
    """A fenced code block: the tag lowercased, `not_specified` when absent, and the line of its
    opening fence."""

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


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CODE_RUN = re.compile("`+")
_LINK = re.compile(r'\[[^\[\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_URL = re.compile(r"https?://\S+")
_PATH_PREFIX = re.compile(r"^(\./|\.\./|/|~/|[A-Za-z]:[\\/])")


def read_text(path: Path) -> str:
    """The text of a file. Raises `PromptError` when it cannot be read: missing, a directory,
    not UTF-8, a path that cannot be one."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise PromptError(f"{path}: {e}") from e


def read(path: Path, root: Path | None = None) -> Prompt:
    """Load a file as a prompt. Raises `PromptError` as `read_text` does, or when the file
    opens a `---` frontmatter block on line 1 that never closes."""
    text = read_text(path)
    lines = text.splitlines()
    if lines and lines[0] == "---" and "---" not in lines[1:]:
        raise PromptError("frontmatter: unclosed --- block opened at line 1")
    return Prompt(text, path, root)


def _scan(prompt: Prompt) -> Iterator[tuple[int, str, Fence | None]]:
    """Every line, numbered, with the fence it opens, sits in or closes; None outside fences."""
    fence: Fence | None = None
    marker = ""
    for no, line in enumerate(prompt.text.splitlines(), 1):
        m = _FENCE.match(line)
        if fence is None and m and not (m[1][0] == "`" and "`" in m[2]):
            marker = m[1]
            fence = Fence((m[2].split() or ["not_specified"])[0].lower(), no)
            yield no, line, fence
        elif fence and m and m[1][0] == marker[0] and len(m[1]) >= len(marker) and not m[2].strip():
            yield no, line, fence
            fence = None
        else:
            yield no, line, fence


def _outside(prompt: Prompt) -> Iterator[tuple[int, str]]:
    return ((no, line) for no, line, fence in _scan(prompt) if fence is None)


def fences(prompt: Prompt) -> list[Fence]:
    """Fenced blocks, in order. Three or more backticks or tildes open one; the closing fence is the
    same character and at least as long; an unclosed fence runs to the end."""
    return [fence for no, _, fence in _scan(prompt) if fence and fence.line == no]


def links(prompt: Prompt) -> list[Link]:
    """Inline `[text](target)` links and `![alt](target)` images outside fences and inline code
    spans, in order; a `"title"` after the target is allowed."""
    return [Link(m[1], no) for no, line in _outside(prompt) for m in _LINK.finditer(_no_spans(line))]


def _no_spans(line: str) -> str:
    """The line without its inline code spans, as in CommonMark: a backtick run opens a span that
    the next run of exactly the same length closes; a run with no such partner is literal text."""
    runs = [m.span() for m in _CODE_RUN.finditer(line)]
    partner: dict[int, int] = {}  # run index -> index of the next run of the same length
    nearest: dict[int, int] = {}  # run length -> index of the nearest such run to the right
    for k in reversed(range(len(runs))):
        n = runs[k][1] - runs[k][0]
        if n in nearest:
            partner[k] = nearest[n]
        nearest[n] = k
    kept, pos, k = [], 0, 0
    while k < len(runs):
        if k in partner:
            kept.append(line[pos:runs[k][0]])
            pos, k = runs[partner[k]][1], partner[k]
        k += 1
    return "".join(kept) + line[pos:]


def headings(prompt: Prompt) -> list[str]:
    """GitHub slugs of the ATX headings outside fences, in order; duplicates get `-1`, `-2`, ..."""
    slugs = []
    seen: Counter[str] = Counter()
    for _, line in _outside(prompt):
        if m := _HEADING.match(line):
            slug = re.sub(r"[^\w\s-]", "", m[1].lower()).replace(" ", "-")
            slugs.append(f"{slug}-{seen[slug]}" if seen[slug] else slug)
            seen[slug] += 1
    return slugs


def _is_path(token: str) -> bool:
    if not re.search(r"[/\\]", token) or "://" in token:
        return False
    last = re.split(r"[/\\]", token)[-1]
    return bool(_PATH_PREFIX.match(token)) or last == "" or "." in last


def paths(prompt: Prompt) -> list[Token]:
    """Path-looking tokens outside fences, stripped of surrounding quotes and trailing punctuation."""
    return [
        Token(token, no)
        for no, line in _outside(prompt)
        for raw in re.split(r"[\s\[\]()]+", line)
        if _is_path(token := raw.rstrip(".,:;").strip("`'\""))
    ]


def urls(prompt: Prompt) -> list[Token]:
    """`http(s)://` URLs anywhere, fences included, trailing punctuation stripped."""
    return [
        Token(m[0].rstrip(".,;:!?)]}>'\"`"), no)
        for no, line in enumerate(prompt.text.splitlines(), 1)
        for m in _URL.finditer(line)
    ]


def host(url: str) -> str:
    """The host of a URL: lowercased, without port or credentials. A bracketed host that is not
    an IPv6 address, such as a `[your-host]` placeholder, keeps its brackets."""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        netloc = re.split(r"[/?#]", url)[2].rpartition("@")[2]
        return re.sub(r"(?<=\]):.*", "", netloc).lower()
