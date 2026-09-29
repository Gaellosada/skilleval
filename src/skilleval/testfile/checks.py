"""One check entry: which names exist under which key, the parameters each takes, and the
normalised `Check` the loader keeps. The checks themselves run in `skilleval.static`, whose
`CHECKS` registry lists the same names."""

import re
from collections.abc import Callable
from functools import partial, reduce
from pathlib import Path
from typing import Any, Literal

from skilleval.testfile.paths import Resolver, glob_to_regex
from skilleval.testfile.schema import Check, LoadError, Severity, at

Family = Literal["lint", "format", "constraints"]
FAMILY: dict[str, Family] = {
    # lint: built-in rules with nothing to configure
    "chars": "lint", "markdown_links": "lint", "paths_exist": "lint",
    # format: the conventions of a named file format
    "anthropic-skill": "format", "anthropic-agent": "format", "anthropic-claude": "format",
    # constraints: thresholds, word lists and policies the user sets
    "words": "constraints", "lines": "constraints",
    "contains": "constraints", "contains_any": "constraints", "contains_none": "constraints",
    "matches": "constraints", "matches_any": "constraints", "matches_none": "constraints",
    "paths": "constraints", "urls": "constraints", "code": "constraints",
}


class Invalid(ValueError):
    """A bad parameter; `parts` locate it below the entry's key."""

    def __init__(self, message: str, *parts: str | int) -> None:
        super().__init__(message)
        self.parts = parts


Reader = Callable[[object], Any]


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Invalid(f"expected a non-negative integer, not {value!r}")
    return value


def _bound(value: object) -> dict[str, int | None]:
    """`{min, max}` with at least one of them, min at most max."""
    if not isinstance(value, dict):
        raise Invalid(f"a bound is a mapping of min and/or max, not {value!r}")
    for k in value:
        if k not in ("min", "max"):
            raise Invalid(f"unknown key {k!r}; a bound takes min and max", k)
    if not value:
        raise Invalid("a bound needs min, max or both")
    bound = {k: _located(_int, value[k], k) if k in value else None for k in ("min", "max")}
    if bound["min"] is not None and bound["max"] is not None and bound["min"] > bound["max"]:
        raise Invalid(f"min {bound['min']} is above max {bound['max']}")
    return bound


def _occurrences(value: object) -> dict[str, int | None]:
    if isinstance(value, dict):
        return _bound(value)
    exact = _int(value)
    return {"min": exact, "max": exact}


def choice(*options: str) -> Reader:
    def read(value: object) -> str:
        if not isinstance(value, str) or value not in options:
            raise Invalid(f"expected one of {', '.join(options)}, not {value!r}")
        return value

    return read


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise Invalid(f"expected true or false, not {value!r}")
    return value


def strings(value: object) -> list[str]:
    """A string or a list of strings, as a list. Raises `ValueError` naming the value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise Invalid(f"expected a string or a list of strings, not {value!r}")


def globs(value: object) -> list[str]:
    """`strings`, each one a glob that compiles; a bad one is located at its index in a list."""
    patterns = strings(value)
    for i, glob in enumerate(patterns):
        try:
            glob_to_regex(glob)
        except re.error as e:
            raise Invalid(f"invalid glob {glob!r}: {e}", *([i] if isinstance(value, list) else [])) from e
    return patterns


def _read_list(path: str, resolve: Resolver) -> list[str]:
    """The non-blank lines of the list file at `path`, stripped."""
    try:
        file = resolve(path)
    except ValueError as e:
        raise Invalid(str(e)) from e
    try:
        text = file.read_text(encoding="utf-8-sig")
    except (OSError, ValueError) as e:
        raise Invalid(f"cannot read {path!r}: {e}") from e
    return [line.strip() for line in text.splitlines() if line.strip()]


def _entries(value: object, *, resolve: Resolver, patterns: bool) -> list[str]:
    """`words` or `patterns`: a string holding `/` is a file with one entry per non-blank
    line, stripped; otherwise one string or a list of them. Never empty, no entry blank;
    every pattern compiles."""
    entries = _read_list(value, resolve) if isinstance(value, str) and "/" in value else strings(value)
    if not entries:
        raise Invalid(f"{value!r} holds no entries")
    for i, entry in enumerate(entries):
        if not entry.strip():
            raise Invalid(f"entry {entry!r} is blank; remove it", i)
        if patterns:
            try:
                re.compile(entry, re.MULTILINE)
            except re.error as e:
                raise Invalid(f"invalid pattern {entry!r}: {e}", i) from e
    return entries


def _located[T, R](read: Callable[[T], R], value: T, part: str | int) -> R:
    """Run a reader on the value under `part`, locating its error below `part`."""
    try:
        return read(value)
    except Invalid as e:
        raise Invalid(str(e), part, *e.parts) from e


def read_at[T, R](read: Callable[[T], R], value: T, path: Path, key: str) -> R:
    """Run a reader on the value written at `key` of the file at `path`. Raises `LoadError`
    there, or below it where the reader locates its error."""
    try:
        return read(value)
    except Invalid as e:
        raise LoadError(path, reduce(at, e.parts, key), str(e)) from e


def severity_of(entry: dict[str, Any]) -> Severity | None:
    """The `severity` a mapping writes, None when it writes none."""
    severity: Severity | None = entry.get("severity")
    if severity not in (None, "error", "warn"):
        raise Invalid(f"severity is error or warn, not {severity!r}", "severity")
    return severity


_POLICY: dict[str, Reader] = {"count": _bound, "default": choice("allow", "deny"), "except": strings}
PARAMS: dict[str, dict[str, Reader]] = {
    "contains": {"occurrences": _occurrences, "case_sensitive": _bool},
    "contains_any": {"occurrences": _occurrences, "case_sensitive": _bool},
    "contains_none": {"case_sensitive": _bool},
    "matches": {"occurrences": _occurrences},
    "matches_any": {"occurrences": _occurrences},
    "matches_none": {},
    "paths": {"count": _bound, "style": choice("posix", "windows"), "except": globs},
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
        readers[LIST_PARAM[name]] = partial(_entries, resolve=resolve, patterns=LIST_PARAM[name] == "patterns")
    params: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in readers:
            raise Invalid(f"unknown parameter {k!r}", k)
        params[k] = _located(readers[k], v, k)
    if name in LIST_PARAM and LIST_PARAM[name] not in params:
        raise Invalid(f"{LIST_PARAM[name]} is required", LIST_PARAM[name])
    if "occurrences" in readers:
        params.setdefault("occurrences", {"min": 1, "max": None})
    if "case_sensitive" in readers:
        params.setdefault("case_sensitive", False)
    if name in ("urls", "code") and "except" in params and "default" not in params:
        raise Invalid("except requires default: allow or deny", "except")
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
        raise LoadError(path, key, f"a check is a name or a one-key mapping of name to parameters, not {entry!r}")
    name, raw = next(iter(entry.items()))
    if FAMILY.get(name) != family:
        raise LoadError(path, key, f"{name!r} is not a {family} check; the {family} checks are "
                        f"{', '.join(sorted(n for n, f in FAMILY.items() if f == family))}")
    return read_at(partial(_check, name, resolve=resolve), raw, path, at(key, name))


def _check(name: str, raw: object, *, resolve: Resolver) -> Check:
    """The check `name` from what its entry holds: parameters, or the list alone of a
    `contains*` or `matches*`."""
    if isinstance(raw, dict):
        params = {k: v for k, v in raw.items() if k != "severity"}
        return Check(name, _params(name, params, resolve), severity_of(raw))
    if name in LIST_PARAM:
        return Check(name, _params(name, {LIST_PARAM[name]: raw}, resolve))
    raise Invalid(f"parameters are a mapping, not {raw!r}; a check without parameters is its name alone, or {{}}")


def read_constraints(value: object, *, path: Path, key: str, resolve: Resolver) -> tuple[Check, ...]:
    """The checks of a list of constraint entries written at `key`, in file order. Raises `LoadError`."""
    return tuple(
        parse_check("constraints", entry, path=path, key=at(key, i), resolve=resolve)
        for i, entry in enumerate(_list(value, path, key))
    )


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
    constraints = body.get("constraints", [])
    checks.extend(read_constraints(constraints, path=path, key=at(key, "constraints"), resolve=resolve))
    return tuple(checks)


def _list(value: object, path: Path, key: str) -> list[object]:
    if not isinstance(value, list):
        raise LoadError(path, key, f"expected a list of check entries, not {value!r}")
    return value
