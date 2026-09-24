"""One check entry: which names exist under which key, the parameters each takes, and the
normalised `Check` the loader keeps. The checks themselves run in `skilleval.static`, whose
`CHECKS` registry lists the same names."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

LINT = frozenset({"chars", "markdown_links", "paths_exist"})
FORMATS = frozenset({"anthropic-skill", "anthropic-claude"})
CONSTRAINTS = frozenset({
    "words", "lines",
    "contains", "contains_any", "contains_none",
    "matches", "matches_any", "matches_none",
    "paths", "urls", "code",
})
Family = Literal["lint", "format", "constraints"]


@dataclass(frozen=True)
class Check:
    """One check entry with its parameters normalised.

    A lint or format is identified by its name: it appears once per test, and a template's
    entry of the same name merges with it. A constraint is an instance: two `words` entries
    are two checks.

    `params` holds only what the entry wrote, after validation and normalisation:
    - a bound (`min`/`max` on `words`, `lines`, `count`, `occurrences`) is always
      `{"min": int | None, "max": int | None}`; `occurrences: 4` becomes min 4, max 4, and
      `occurrences` on `contains`, `contains_any`, `matches`, `matches_any` defaults to
      `{"min": 1, "max": None}`;
    - `words` and `patterns` are always lists of strings, read from the file when given as a
      path; `contains: Usage` becomes `{"words": ["Usage"], ...}`; `case_sensitive` on the
      `contains*` checks defaults to False; every pattern compiles, and is compiled again
      with `re.MULTILINE` when the check runs;
    - `except` is always a list;
    - lint and format checks have no parameters: `{}`.
    """

    name: str
    params: dict[str, Any] = field(default_factory=dict)
    severity: Literal["error", "warn"] = "error"


def parse_check(
    family: Family, entry: object, *, path: Path, key: str, resolve: Callable[[str], Path]
) -> Check:
    """Turn one entry of `lint`, `format` or `constraints` (the `family`) into a `Check`.

    `entry` is a bare name or a one-key mapping of name to parameters, `severity` included.
    `key` is the entry's dotted location in the file, for errors; `resolve` turns a path
    written in the file into an absolute one, for word lists. Raises `LoadError` at `key`,
    or at `key.<parameter>` for a bad parameter, naming the value.
    """
    raise NotImplementedError
