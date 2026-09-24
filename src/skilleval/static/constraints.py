"""Constraints: everything the user decides — thresholds, word lists, policies."""

from typing import Any

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def words(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def lines(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def contains(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def contains_any(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def contains_none(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def matches(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """Occurrences are non-overlapping, as `re.finditer` counts them."""
    raise NotImplementedError


def matches_any(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def matches_none(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def paths(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def urls(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def code(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


CHECKS: dict[str, CheckFunction] = {
    "words": words, "lines": lines,
    "contains": contains, "contains_any": contains_any, "contains_none": contains_none,
    "matches": matches, "matches_any": matches_any, "matches_none": matches_none,
    "paths": paths, "urls": urls, "code": code,
}
