"""Constraints: everything the user decides — thresholds, word lists, policies."""

from __future__ import annotations

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def words(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def lines(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def contains(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def contains_any(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def contains_none(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def matches(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def matches_any(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def matches_none(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    raise NotImplementedError


def paths(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """Detected: every path seen, `except` applied or not."""
    raise NotImplementedError


def urls(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """Detected: every URL seen."""
    raise NotImplementedError


def code(prompt: Prompt, params: dict) -> tuple[list[Finding], list[str]]:
    """Detected: the tag of every fenced block."""
    raise NotImplementedError


CHECKS: dict[str, CheckFunction] = {f.__name__: f for f in (
    words, lines, contains, contains_any, contains_none,
    matches, matches_any, matches_none, paths, urls, code,
)}
