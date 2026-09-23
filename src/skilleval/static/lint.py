"""Lint: built-in rules with nothing to configure."""

from __future__ import annotations


def chars(prompt, params):
    """No invisible characters: one finding per occurrence, with its line and codepoint."""
    raise NotImplementedError


def markdown_links(prompt, params):
    """Every inline link resolves: the target exists and its `#anchor` matches a heading."""
    raise NotImplementedError


def paths_exist(prompt, params):
    """Every path mentioned outside fences exists. Detected: every path seen."""
    raise NotImplementedError


CHECKS = {"chars": chars, "markdown_links": markdown_links, "paths_exist": paths_exist}
