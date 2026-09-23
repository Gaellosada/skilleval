"""Constraints: everything the user decides — thresholds, word lists, policies."""

from __future__ import annotations


def words(prompt, params):
    raise NotImplementedError


def lines(prompt, params):
    raise NotImplementedError


def contains(prompt, params):
    raise NotImplementedError


def contains_any(prompt, params):
    raise NotImplementedError


def contains_none(prompt, params):
    raise NotImplementedError


def matches(prompt, params):
    raise NotImplementedError


def matches_any(prompt, params):
    raise NotImplementedError


def matches_none(prompt, params):
    raise NotImplementedError


def paths(prompt, params):
    """Detected: every path seen, `except` applied or not."""
    raise NotImplementedError


def urls(prompt, params):
    """Detected: every URL seen."""
    raise NotImplementedError


def code(prompt, params):
    """Detected: the tag of every fenced block."""
    raise NotImplementedError


CHECKS = {f.__name__: f for f in (
    words, lines, contains, contains_any, contains_none,
    matches, matches_any, matches_none, paths, urls, code,
)}
