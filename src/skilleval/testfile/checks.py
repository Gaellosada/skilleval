"""One check entry: which names exist under which key, the parameters each takes, and the
normalised `Check` the loader keeps. The checks themselves run in `skilleval.static`, whose
`CHECKS` registry lists the same names."""

import re
from collections.abc import Callable
from functools import partial, reduce
from pathlib import Path
from typing import Any, Literal

from skilleval.testfile.paths import Resolver, glob_to_regex
from skilleval.testfile.schema import Check, LoadError, at

Family = Literal["lint", "format", "constraints"]
FAMILY: dict[str, Family] = {
    # lint: built-in rules with nothing to configure
    "chars": "lint", "markdown_links": "lint", "paths_exist": "lint",
    # format: the conventions of a named file format
    "anthropic-skill": "format", "anthropic-claude": "format",
    # constraints: thresholds, word lists and policies the user sets
    "words": "constraints", "lines": "constraints",
    "contains": "constraints", "contains_any": "constraints", "contains_none": "constraints",
    "matches": "constraints", "matches_any": "constraints", "matches_none": "constraints",
    "paths": "constraints", "urls": "constraints", "code": "constraints",
}


class _Invalid(ValueError):
    """A bad parameter; `parts` locate it below the entry's key."""

    def __init__(self, message: str, *parts: str | int) -> None:
        super().__init__(message)
        self.parts = parts


Reader = Callable[[object], Any]


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _Invalid(f"expected a non-negative integer, not {value!r}")
    return value


def _bound(value: object) -> dict[str, int | None]:
    """`{min, max}` with at least one of them, min at most max."""
    if not isinstance(value, dict):
        raise _Invalid(f"a bound is a mapping of min and/or max, not {value!r}")
    for k in value:
        if k not in ("min", "max"):
            raise _Invalid(f"unknown key {k!r}; a bound takes min and max", k)
    if not value:
        raise _Invalid("a bound needs min, max or both")
    bound = {k: _located(_int, value[k], k) if k in value else None for k in ("min", "max")}
    if bound["min"] is not None and bound["max"] is not None and bound["min"] > bound["max"]:
        raise _Invalid(f"min {bound['min']} is above max {bound['max']}")
    return bound


def _occurrences(value: object) -> dict[str, int | None]:
    if isinstance(value, dict):
        return _bound(value)
    exact = _int(value)
    return {"min": exact, "max": exact}


def _choice(*options: str) -> Reader:
    def read(value: object) -> str:
        if not isinstance(value, str) or value not in options:
            raise _Invalid(f"expected one of {', '.join(options)}, not {value!r}")
        return value

    return read


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise _Invalid(f"expected true or false, not {value!r}")
    return value


def strings(value: object) -> list[str]:
    """A string or a list of strings, as a list. Raises `ValueError` naming the value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise _Invalid(f"expected a string or a list of strings, not {value!r}")


def _globs(value: object) -> list[str]:
    """`strings`, each one a glob that compiles."""
    globs = strings(value)
    for i, glob in enumerate(globs):
        try:
            glob_to_regex(glob)
        except re.error as e:
            raise _Invalid(f"invalid glob {glob!r}: {e}", i) from e
    return globs


def _entries(value: object, *, resolve: Resolver, patterns: bool) -> list[str]:
    """`words` or `patterns`: a string holding `/` is a file with one entry per non-blank
    line; otherwise one string or a list of them. Never empty, no entry blank; every pattern
    compiles."""
    if isinstance(value, str) and "/" in value:
        try:
            text = resolve(value).read_text(encoding="utf-8")
        except (OSError, ValueError) as e:
            raise _Invalid(f"cannot read {value!r}: {e}") from e
        entries = [line for line in text.splitlines() if line.strip()]
    else:
        entries = strings(value)
    if not entries:
        raise _Invalid(f"{value!r} holds no entries")
    for i, entry in enumerate(entries):
        if not entry.strip():
            raise _Invalid(f"entry {entry!r} is blank; remove it", i)
        if patterns:
            try:
                re.compile(entry, re.MULTILINE)
            except re.error as e:
                raise _Invalid(f"invalid pattern {entry!r}: {e}", i) from e
    return entries


def _located[T, R](read: Callable[[T], R], value: T, part: str | int) -> R:
    """Run a reader on the value under `part`, locating its error below `part`."""
    try:
        return read(value)
    except _Invalid as e:
        raise _Invalid(str(e), part, *e.parts) from e


_POLICY: dict[str, Reader] = {"count": _bound, "default": _choice("allow", "deny"), "except": strings}
PARAMS: dict[str, dict[str, Reader]] = {
    "contains": {"occurrences": _occurrences, "case_sensitive": _bool},
    "contains_any": {"occurrences": _occurrences, "case_sensitive": _bool},
    "contains_none": {"case_sensitive": _bool},
    "matches": {"occurrences": _occurrences},
    "matches_any": {"occurrences": _occurrences},
    "matches_none": {},
    "paths": {"count": _bound, "style": _choice("posix", "windows"), "except": _globs},
    "urls": _POLICY,
    "code": _POLICY,
}
LIST_PARAM = {
    "contains": "words", "contains_any": "words", "contains_none": "words",
    "matches": "patterns", "matches_any": "patterns", "matches_none": "patterns",
}


def _params(name: str, raw: dict[str, Any], resolve: Resolver) -> dict[str, Any]:
    """The parameters of one entry, `severity` already removed, validated and normalised."""
    if name in ("words", "lines"):
        return _bound(raw)
    readers = dict(PARAMS.get(name, {}))
    if name in LIST_PARAM:
        entries = partial(_entries, resolve=resolve, patterns=LIST_PARAM[name] == "patterns")
        readers[LIST_PARAM[name]] = entries
    params: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in readers:
            raise _Invalid(f"unknown parameter {k!r}", k)
        params[k] = _located(readers[k], v, k)
    if name in LIST_PARAM and LIST_PARAM[name] not in params:
        raise _Invalid(f"{LIST_PARAM[name]} is required", LIST_PARAM[name])
    if "occurrences" in readers:
        params.setdefault("occurrences", {"min": 1, "max": None})
    if "case_sensitive" in readers:
        params.setdefault("case_sensitive", False)
    if name in ("urls", "code") and "except" in params and "default" not in params:
        raise _Invalid("except requires default: allow or deny", "except")
    return params


def parse_check(family: Family, entry: object, *, path: Path, key: str, resolve: Resolver) -> Check:
    """Turn one entry of `lint`, `format` or `constraints` (the `family`) into a `Check`.

    `entry` is a bare name or a one-key mapping of name to parameters, `severity` included.
    `key` is the entry's dotted location in the file, for errors; `resolve` turns a path
    written in the file into an absolute one, for word lists. Raises `LoadError` at `key`,
    or at `key.<parameter>` for a bad parameter, naming the value.
    """
    if isinstance(entry, str):
        entry = {entry: {}}
    if not (isinstance(entry, dict) and len(entry) == 1):
        raise LoadError(
            path, key, f"a check is a name or a one-key mapping of name to parameters, not {entry!r}"
        )
    name, raw = next(iter(entry.items()))
    if FAMILY.get(name) != family:
        raise LoadError(path, key, f"{name!r} is not a {family} check; the {family} checks are "
                        f"{', '.join(sorted(n for n, f in FAMILY.items() if f == family))}")
    try:
        if isinstance(raw, dict):
            raw = dict(raw)
            severity = raw.pop("severity", "error")
            if severity not in ("error", "warn"):
                raise _Invalid(f"severity is error or warn, not {severity!r}", "severity")
        elif name in LIST_PARAM:
            raw, severity = {LIST_PARAM[name]: raw}, "error"
        else:
            raise _Invalid(f"parameters are a mapping, not {raw!r}")
        return Check(name, _params(name, raw, resolve), severity)
    except _Invalid as e:
        raise LoadError(path, reduce(at, e.parts, at(key, name)), str(e)) from e


def read_checks(body: dict[str, Any], *, path: Path, key: str, resolve: Resolver) -> tuple[Check, ...]:
    """The checks of a test or template body: its `lint` list, `format` and `constraints`
    list, in that order and file order within each. A lint named twice is an error."""
    checks: list[Check] = []
    for i, entry in enumerate(_list(body.get("lint", []), path, at(key, "lint"))):
        entry_key = at(at(key, "lint"), i)
        check = parse_check("lint", entry, path=path, key=entry_key, resolve=resolve)
        if any(c.name == check.name for c in checks):
            raise LoadError(path, entry_key, f"lint {check.name!r} is named twice")
        checks.append(check)
    if "format" in body:
        checks.append(parse_check("format", body["format"], path=path, key=at(key, "format"), resolve=resolve))
    for i, entry in enumerate(_list(body.get("constraints", []), path, at(key, "constraints"))):
        entry_key = at(at(key, "constraints"), i)
        checks.append(parse_check("constraints", entry, path=path, key=entry_key, resolve=resolve))
    return tuple(checks)


def _list(value: object, path: Path, key: str) -> list[object]:
    if not isinstance(value, list):
        raise LoadError(path, key, f"expected a list of check entries, not {value!r}")
    return value
