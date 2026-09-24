"""Lint: built-in rules with nothing to configure."""

from typing import Any

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def chars(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """No invisible characters: one finding per occurrence, with its line and codepoint."""
    raise NotImplementedError


def markdown_links(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every inline link resolves: the target exists and its `#anchor` matches a heading."""
    raise NotImplementedError


def paths_exist(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Every path mentioned outside fences exists."""
    raise NotImplementedError


CHECKS: dict[str, CheckFunction] = {
    "chars": chars, "markdown_links": markdown_links, "paths_exist": paths_exist,
}
