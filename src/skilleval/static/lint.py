"""Lint: built-in rules with nothing to configure."""

import unicodedata
from pathlib import Path
from typing import Any

from skilleval.static.prompt import Prompt, PromptError, headings, links, paths, read
from skilleval.static.result import CheckFunction, Finding

INVISIBLE = frozenset("﻿  ​‌‍⁠")


def chars(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """No invisible characters: one finding per occurrence, with its line and codepoint."""
    return [
        Finding(f"invisible character U+{ord(c):04X} ({unicodedata.name(c).lower()})", no)
        for no, line in enumerate(prompt.text.splitlines(), 1)
        for c in line
        if c in INVISIBLE
    ]


def markdown_links(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every inline link resolves: the target exists and its `#anchor` matches a heading."""
    assert prompt.path is not None
    findings = []
    for link in links(prompt):
        if link.target.startswith(("http://", "https://")):
            continue
        path, _, anchor = link.target.partition("#")
        target = None
        if path:
            if path.startswith("/"):
                if prompt.root is None:
                    findings.append(Finding(f"{path} is relative to the project root, "
                                            "and the file declares no root", link.line))
                    continue
                target = prompt.root / path.lstrip("/")
            else:
                target = prompt.path.parent / path
            if not target.exists():
                findings.append(Finding(f"{path} does not exist", link.line))
                continue
        if not anchor:
            continue
        try:
            slugs = headings(read(target) if target else prompt)
        except PromptError:
            slugs = []
        if anchor not in slugs:
            where = path or "this file"
            findings.append(Finding(f"#{anchor} matches no heading in {where}", link.line))
    return findings


def paths_exist(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every path mentioned outside fences exists."""
    assert prompt.path is not None
    directory = prompt.path.parent
    return [
        Finding(f"{token.text} does not exist", token.line)
        for token in paths(prompt)
        if not (directory / Path(token.text).expanduser()).exists()
    ]


CHECKS: dict[str, CheckFunction] = {
    "chars": chars, "markdown_links": markdown_links, "paths_exist": paths_exist,
}
