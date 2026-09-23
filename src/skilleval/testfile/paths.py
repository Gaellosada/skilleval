"""Paths and globs written in a test file. Specified in specs/README.md and specs/static-checking.md."""

from __future__ import annotations

import re
from pathlib import Path


def find_root(file: Path, marker: str) -> Path:
    """The nearest ancestor of `file` holding `marker`, a file or a directory. Raises
    `FileNotFoundError` when none does."""
    raise NotImplementedError


def resolve(written: str, file: Path, root: Path | None) -> Path:
    """A path as written in the file: `./x` from the file's directory, anything else from
    `root`. Raises `ValueError` for a root-relative path when `root` is None."""
    raise NotImplementedError


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """The glob syntax of `exclude` on a prompt and `except` on `paths`: `*`, `?`, `[...]`
    stop at `/`, `**` crosses it. The regex matches the whole token; `**/` also matches
    nothing, so `**/fixtures/**` matches `fixtures/a.md`."""
    raise NotImplementedError
