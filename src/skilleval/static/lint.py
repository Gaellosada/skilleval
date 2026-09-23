"""Lint: built-in rules with nothing to configure."""

from __future__ import annotations

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def chars(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """No invisible characters: one finding per occurrence, with its line and codepoint."""
    raise NotImplementedError


def markdown_links(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """Every inline link resolves: the target exists and its `#anchor` matches a heading."""
    raise NotImplementedError


def paths_exist(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """Every path mentioned outside fences exists. Detected: every path seen."""
    raise NotImplementedError


CHECKS: dict[str, CheckFunction] = {
    "chars": chars, "markdown_links": markdown_links, "paths_exist": paths_exist,
}
