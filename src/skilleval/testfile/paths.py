"""Paths and globs written in a test file. Specified in specs/README.md and specs/static-checking.md."""

import os
import re
from collections.abc import Callable
from pathlib import Path

Resolver = Callable[[str], Path]
HOME = ".skilleval"  # the folder of a project where skilleval, alone, keeps the results and the settings


def find_root(file: Path, marker: str) -> Path:
    """The nearest ancestor of `file` holding `marker`, a file or a directory. Raises
    `FileNotFoundError` when none does."""
    for directory in file.absolute().parents:
        if (directory / marker).exists():
            return directory
    raise FileNotFoundError(f"no ancestor of {file} holds {marker}")


def base(written: str, file: Path, root: Path | None) -> Path:
    """Where a path or glob written in the file starts: the file's directory for `./x`,
    `root` for any other, which an absolute path discards when joined to it. Raises
    `ValueError` for any other when `root` is None."""
    if written.startswith("./"):
        return file.parent
    if root is None:
        raise ValueError(f"{written} is not a ./ path, and the file declares no root")
    return root


def resolve(written: str, file: Path, root: Path | None) -> Path:
    """A path as written in the file, from its `base` (an absolute one stays as is);
    normalised lexically (`os.path.normpath`), no filesystem access. Raises `ValueError`
    as `base` does."""
    return Path(os.path.normpath(base(written, file, root) / written))


_GLOB_TOKEN = re.compile(r"\*\*/|\*\*|\[(!?+)(\]?+[^\]]*)\]|.")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """The glob syntax of `exclude` on a prompt and `except` on `paths`: `*`, `?`, `[...]`
    stop at a separator, `/` or `\\`, and `**` crosses it. A class reads as in `fnmatch`:
    `[!...]` negates, a `]` first in it is literal, ranges stay and every other character
    is literal; an unclosed `[` is a literal bracket. The regex is anchored at both ends;
    `**/` also matches nothing, so `**/fixtures/**` matches `fixtures/a.md`. Raises
    `re.error` for a class that cannot compile, such as the reversed range `[z-a]`."""
    parts = []
    for m in _GLOB_TOKEN.finditer(pattern):
        token = m[0]
        if token == "**/":
            parts.append("(?:.*/)?")
        elif token == "**":
            parts.append(".*")
        elif token == "*":
            parts.append(r"[^/\\]*")
        elif token == "?":
            parts.append(r"[^/\\]")
        elif m[2] is not None:
            body = "".join(c if c == "-" else re.escape(c) for c in m[2])
            parts.append(rf"[^/\\{body}]" if m[1] else rf"(?![/\\])[{body}]")
        else:
            parts.append(re.escape(token))
    return re.compile(f"^{''.join(parts)}$")
