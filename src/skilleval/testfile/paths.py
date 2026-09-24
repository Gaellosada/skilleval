"""Paths and globs written in a test file. Specified in specs/README.md and specs/static-checking.md."""

import os
import re
from collections.abc import Callable
from pathlib import Path

Resolver = Callable[[str], Path]


def find_root(file: Path, marker: str) -> Path:
    """The nearest ancestor of `file` holding `marker`, a file or a directory. Raises
    `FileNotFoundError` when none does."""
    for directory in file.absolute().parents:
        if (directory / marker).exists():
            return directory
    raise FileNotFoundError(f"no ancestor of {file} holds {marker}")


def base(written: str, file: Path, root: Path | None) -> Path:
    """Where a relative path or glob written in the file starts: the file's directory for
    `./x`, `root` for anything else. Raises `ValueError` for a root-relative one when `root`
    is None."""
    if written.startswith("./"):
        return file.parent
    if root is None:
        raise ValueError(f"{written} is relative to the project root, and the file declares no root")
    return root


def resolve(written: str, file: Path, root: Path | None) -> Path:
    """A path as written in the file, absolute or from its `base`; normalised lexically
    (`os.path.normpath`), no filesystem access. Raises `ValueError` as `base` does."""
    if Path(written).is_absolute():
        return Path(os.path.normpath(written))
    return Path(os.path.normpath(base(written, file, root) / written))


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """The glob syntax of `exclude` on a prompt and `except` on `paths`: `*`, `?`, `[...]`
    stop at `/`, `**` crosses it. The regex is anchored at both ends; `**/` also matches
    nothing, so `**/fixtures/**` matches `fixtures/a.md`."""
    parts = []
    for token in re.findall(r"\*\*/|\*\*|\[!?[^\]]*\]|.", pattern):
        if token == "**/":
            parts.append("(?:.*/)?")
        elif token == "**":
            parts.append(".*")
        elif token == "*":
            parts.append("[^/]*")
        elif token == "?":
            parts.append("[^/]")
        elif token.startswith("["):
            negated = token.startswith("[!")
            parts.append(f"[^/{token[2:]}" if negated else token)
        else:
            parts.append(re.escape(token))
    return re.compile(f"^{''.join(parts)}$")
