"""Lint: built-in rules with nothing to configure."""

import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

from skilleval.static.prompt import Prompt, PromptError, headings, links, paths, read
from skilleval.static.result import CheckFunction, Finding

_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")  # two letters or more, so C:/ stays a path
INVISIBLE = frozenset("\ufeff\u00a0\u202f\u200b\u200c\u200d\u2060")


def chars(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """No invisible characters: one finding per occurrence, with its line and codepoint."""
    return [
        Finding(f"invisible character U+{ord(c):04X} ({unicodedata.name(c).lower()})", no)
        for no, line in enumerate(prompt.text.splitlines(), 1)
        for c in line
        if c in INVISIBLE
    ]


def markdown_links(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every inline link resolves: the target exists and its `#anchor` matches a heading.
    A target with a URL scheme (`https:`, `mailto:`, ...) is left alone."""
    findings = []
    slugs = cache(_slugs)  # one read per target file
    for link in links(prompt):
        if _SCHEME.match(link.target):
            continue
        path, _, anchor = link.target.partition("#")
        target = _link_target(path, prompt, link.line) if path else None
        if isinstance(target, Finding):
            findings.append(target)
        elif anchor and anchor not in slugs(target or prompt):
            findings.append(Finding(f"#{anchor} matches no heading in {path or 'this file'}", link.line))
    return findings


def _slugs(source: Path | Prompt) -> list[str]:
    """The heading slugs of a file or prompt; none when the file cannot be read."""
    try:
        return headings(read(source) if isinstance(source, Path) else source)
    except PromptError:
        return []


def _link_target(path: str, prompt: Prompt, line: int) -> Path | Finding:
    """The file a link's `path` names: from `prompt.root` when it starts with `/`, else from
    the prompt's directory. Returns the finding to report instead when it has no root to
    resolve from or does not exist."""
    assert prompt.path is not None
    if path.startswith("/"):
        if prompt.root is None:
            return Finding(f"{path} is relative to the project root, and the file declares no root", line)
        target = prompt.root / path.lstrip("/")
    else:
        target = prompt.path.parent / path
    return target if target.exists() else Finding(f"{path} does not exist", line)


def paths_exist(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every path mentioned outside fences exists. Only `~/` expands; `~user/` is checked as written."""
    assert prompt.path is not None
    directory = prompt.path.parent
    return [
        Finding(f"{token.text} does not exist", token.line)
        for token in paths(prompt)
        if not (directory / (Path.home() / token.text[2:] if token.text.startswith("~/") else token.text)).exists()
    ]


CHECKS: dict[str, CheckFunction] = {
    "chars": chars, "markdown_links": markdown_links, "paths_exist": paths_exist,
}
