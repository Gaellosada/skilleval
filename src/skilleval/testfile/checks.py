"""Reading one check entry: which names exist under which key, and the parameters each takes.

The normalised result is documented on `Check`. The checks themselves run in `skilleval.static`,
whose `CHECKS` registry lists the same names.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skilleval.testfile import Check

LINT = ("chars", "markdown_links", "paths_exist")
FORMATS = ("anthropic-skill", "anthropic-claude")
CONSTRAINTS = (
    "words", "lines",
    "contains", "contains_any", "contains_none",
    "matches", "matches_any", "matches_none",
    "paths", "urls", "code",
)


def parse_check(key: str, entry: object, resolve: Callable[[str], Path]) -> Check:
    """Turn one entry of `lint`, `format` or `constraints` (the `key`) into a `Check`.

    `entry` is a bare name or a one-key mapping of name to parameters, `severity` included.
    `resolve` turns a path written in the file into an absolute one, for word lists. Raises
    `ValueError(sub_key, message)` for a bad name or parameter, where `sub_key` is the
    location inside the entry (`words.max`, `patterns[1]`, empty for the entry itself); the
    loader wraps it into a `LoadError` at the entry's dotted location.
    """
    raise NotImplementedError
