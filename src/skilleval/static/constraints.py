"""Constraints: everything the user decides — thresholds, word lists, policies."""

import re
from typing import Any

from skilleval.static import prompt as detect
from skilleval.static.prompt import Prompt, host
from skilleval.static.result import CheckFunction, Finding
from skilleval.testfile.paths import glob_to_regex


def _bounded(count: int, bound: dict[str, Any], what: str, of: str = "") -> list[Finding]:
    """One finding when `count` falls outside `{"min", "max"}`: `what` is counted, in the
    singular, and `of` says of what. An empty `bound` holds any count."""
    counted = f"{count} {what}{'s' * (count != 1)}{of}"
    if (most := bound.get("max")) is not None and count > most:
        return [Finding(f"{counted}, above the maximum of {most}")]
    if (least := bound.get("min")) is not None and count < least:
        return [Finding(f"{counted}, below the minimum of {least}")]
    return []


def _patterns(params: dict[str, Any]) -> list[tuple[str, re.Pattern[str]]]:
    """The list as written, each entry with its regex: `patterns` compiled, `words` as whole words
    on `\\w` boundaries, a multi-word entry as a phrase."""
    if "patterns" in params:
        return [(p, re.compile(p, re.MULTILINE)) for p in params["patterns"]]
    flags = 0 if params["case_sensitive"] else re.IGNORECASE
    return [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)", flags)) for w in params["words"]]


def each_within(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """`contains` and `matches`: each entry's occurrences within `occurrences`.
    Occurrences are non-overlapping, as `re.findall` counts them."""
    findings = []
    for label, pattern in _patterns(params):
        count = len(pattern.findall(prompt.text))
        findings += _bounded(count, params["occurrences"], "occurrence", f" of {label!r}")
    return findings


def total_within(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """`contains_any` and `matches_any`: the total across the list within `occurrences`."""
    entries = _patterns(params)
    total = sum(len(pattern.findall(prompt.text)) for _, pattern in entries)
    labels = ", ".join(repr(label) for label, _ in entries)
    return _bounded(total, params["occurrences"], "occurrence", f" of any of {labels}")


def none_found(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """`contains_none` and `matches_none`: a finding per entry found, at its first hit."""
    findings = []
    for label, pattern in _patterns(params):
        if m := pattern.search(prompt.text):
            line = len((prompt.text[: m.start()] + "x").splitlines())  # "x" stands for the match's own line
            findings.append(Finding(f"{label!r} found", line))
    return findings


def _policy(params: dict[str, Any], items: list[tuple[str, int, bool]], what: str) -> list[Finding]:
    """`default: allow | deny` plus `except`: a finding per `(label, line, excepted)` on the wrong
    side; then `count`, a bound on how many items there are, each one `what`."""
    findings = []
    if "default" in params:
        allowed = params["default"] == "allow"
        findings = [Finding(f"{label} is not allowed", line) for label, line, excepted in items if excepted == allowed]
    return findings + _bounded(len(items), params.get("count", {}), what)


def _excepted_host(url: str, hosts: list[str]) -> bool:
    h = host(url)
    return any(h == e.lower() or h.endswith("." + e.lower()) for e in hosts)


def words(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    return _bounded(len(prompt.text.split()), params, "word")


def lines(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    return _bounded(len(prompt.text.splitlines()), params, "line")


def paths(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    excepted = [glob_to_regex(g) for g in params.get("except", [])]
    kept = [t for t in detect.paths(prompt) if not any(r.match(t.text) for r in excepted)]
    findings = []
    if style := params.get("style"):
        wrong = "\\" if style == "posix" else "/"
        findings += [Finding(f"{t.text} is not a {style} path", t.line) for t in kept if wrong in t.text]
    return findings + _bounded(len(kept), params.get("count", {}), "path")


def urls(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    hosts = params.get("except", [])
    found = [(t.text, t.line, _excepted_host(t.text, hosts)) for t in detect.urls(prompt)]
    return _policy(params, found, "URL")


def code(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    tags = {e.lower() for e in params.get("except", [])}
    blocks = [(f"code block tagged {f.lang}", f.line, f.lang in tags) for f in detect.fences(prompt)]
    return _policy(params, blocks, "code block")


CHECKS: dict[str, CheckFunction] = {
    "words": words, "lines": lines,
    "contains": each_within, "contains_any": total_within, "contains_none": none_found,
    "matches": each_within, "matches_any": total_within, "matches_none": none_found,
    "paths": paths, "urls": urls, "code": code,
}
