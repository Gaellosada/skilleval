"""Formats: the hard rules Anthropic documents for a `SKILL.md`, a subagent's file and a `CLAUDE.md`,
and those of RFC 8259 for a JSON text.

A skill's fields are `_SKILL` and a subagent's `_AGENT`, one row per field as in the tables of
the spec. A rule gives what is wrong with a value, None when nothing is; the first rule of a
row is the field's type, and the others apply only to a value of that type.
"""

import json
import re
from collections.abc import Callable
from typing import Any, NoReturn, get_args

import yaml

from skilleval.static.prompt import Prompt, frontmatter
from skilleval.static.result import CheckFunction, Finding
from skilleval.testfile import Effort

Rule = Callable[[Any, Prompt], str | None]
Table = dict[str, tuple[Rule, ...]]

_BOOLEANS = ("true", "false", "yes", "no", "on", "off", "1", "0")
_CLAUDE_FILES = ("CLAUDE.md", "CLAUDE.local.md")
_MAX_BYTES = 4 * 2**20


def _mapping(value: Any, _: Prompt) -> str | None:
    return None if isinstance(value, dict) else f"{value!r} is not a mapping"


def _read_as(kind: type, wanted: str) -> Rule:
    """A value of the type `kind` and of no other: a YAML boolean is an `int` for Python, and no integer."""

    def rule(value: Any, _: Prompt) -> str | None:
        if type(value) is kind:
            return None
        written = repr(value) if isinstance(value, str) else value
        return f"YAML reads {written} as {type(value).__name__}, not {wanted}"

    return rule


_string = _read_as(str, "text; quote it")


def _at_least(least: int) -> Rule:
    return lambda value, _: None if value >= least else f"{value} is below the minimum of {least}"


def _length(most: int, least: int = 0) -> Rule:
    def rule(value: str, _: Prompt) -> str | None:
        if len(value) > most:
            return f"{len(value)} characters, above the maximum of {most}"
        if len(value) < least:
            return f"{len(value)} characters, below the minimum of {least}"
        return None

    return rule


def _holds_none(*parts: str) -> Rule:
    def rule(value: str, _: Prompt) -> str | None:
        held = [part for part in parts if part in value]
        return f"{value!r} holds {' and '.join(held)}" if held else None

    return rule


def _one_of(*values: str) -> Rule:
    return lambda value, _: None if value in values else f"{value!r} is not one of {', '.join(values)}"


def _string_or_strings(value: Any, _: Prompt) -> str | None:
    if isinstance(value, str) or (isinstance(value, list) and all(isinstance(v, str) for v in value)):
        return None
    return f"{value!r} is not a string or a list of strings"


def _strings_or_mappings(value: list[Any], _: Prompt) -> str | None:
    if all(isinstance(v, str | dict) for v in value):
        return None
    return f"{value!r} has an entry that is neither a string nor a mapping"


def _boolean(value: Any, _: Prompt) -> str | None:
    if str(value).lower() in _BOOLEANS:
        return None
    return f"{value!r} is not a boolean: one of {', '.join(_BOOLEANS)}, in any letter case"


def _lowercase_hyphenated(value: str, _: Prompt) -> str | None:
    if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value):
        return None
    return f"{value!r} is not lowercase letters a-z and digits, joined by single hyphens"


def _no_hyphen_first(value: str, _: Prompt) -> str | None:
    return f"{value!r} starts with a hyphen" if value.startswith("-") else None


def _names_its_directory(value: str, prompt: Prompt) -> str | None:
    if prompt.path is None:
        return None
    directory = prompt.path.absolute().parent.name
    return None if value == directory else f"{value!r} is not the name of its directory, {directory}"


def _not_blank(value: str, _: Prompt) -> str | None:
    return None if value.strip() else f"{value!r} is blank"


def _strings_to_strings(value: dict[Any, Any], _: Prompt) -> str | None:
    if all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        return None
    return f"{value!r} has a key or a value that is not a string"


_EFFORT = (_string, _one_of(*get_args(Effort)))
_SKILL: Table = {
    "name": (_string, _length(64), _lowercase_hyphenated, _holds_none("anthropic", "claude"), _names_its_directory),
    "description": (_string, _not_blank, _length(1024), _holds_none("<", ">")),
    "compatibility": (_string, _length(500, least=1)),
    **dict.fromkeys(("license", "when_to_use", "argument-hint", "model", "agent"), (_string,)),
    "metadata": (_mapping, _strings_to_strings),
    "hooks": (_mapping,),
    **dict.fromkeys(("allowed-tools", "disallowed-tools", "arguments", "paths"), (_string_or_strings,)),
    **dict.fromkeys(("disable-model-invocation", "user-invocable", "background"), (_boolean,)),
    "effort": _EFFORT,
    "context": (_string, _one_of("fork")),
    "shell": (_string, _one_of("bash", "powershell")),
}
_AGENT: Table = {
    "name": (_string, _not_blank, _holds_none(":"), _no_hyphen_first),
    "description": (_string, _not_blank),
    **dict.fromkeys(("model", "initialPrompt"), (_string,)),
    **dict.fromkeys(("tools", "disallowedTools", "skills"), (_string_or_strings,)),
    "mcpServers": (_read_as(list, "a list"), _strings_or_mappings),
    **dict.fromkeys(("hooks", "experimental"), (_mapping,)),
    "maxTurns": (_read_as(int, "an integer"), _at_least(1)),
    **dict.fromkeys(("background", "omitClaudeMd"), (_boolean,)),
    "permissionMode": (
        _string, _one_of("default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"),
    ),
    "memory": (_string, _one_of("user", "project", "local")),
    "effort": _EFFORT,
    "isolation": (_string, _one_of("worktree")),
    "color": (_string, _one_of("red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan")),
}


def _problems(value: Any, rules: tuple[Rule, ...], prompt: Prompt) -> list[str]:
    """What `rules` find wrong with `value`: its type alone when that is wrong."""
    if value is None:
        return ["written without a value"]
    is_type, *others = rules
    if wrong := is_type(value, prompt):
        return [wrong]
    return [problem for rule in others if (problem := rule(value, prompt))]


def _frontmatter_findings(prompt: Prompt, table: Table) -> list[Finding]:
    """The findings of the frontmatter: a YAML mapping, whose fields `table` checks."""
    cut = frontmatter(prompt.text)
    if cut is None:
        return [Finding("no frontmatter: the first line and a later one must be ---")]
    try:
        fields = yaml.safe_load(cut)
    except (yaml.YAMLError, ValueError, RecursionError) as e:  # ValueError: a date that does not exist
        reason = e.problem if isinstance(e, yaml.MarkedYAMLError) else str(e).splitlines()[0]
        return [Finding(f"the frontmatter does not parse as YAML: {reason}")]
    if not isinstance(fields, dict):
        written = "empty" if fields is None else repr(fields)
        return [Finding(f"the frontmatter is {written}, not a mapping of fields")]
    findings = [Finding(f"{field}: not a documented field") for field in fields if field not in table]
    findings += [Finding(f"{field}: missing") for field in ("name", "description") if field not in fields]
    return findings + [
        Finding(f"{field}: {problem}")
        for field, value in fields.items()
        if field in table
        for problem in _problems(value, table[field], prompt)
    ]


def anthropic_skill(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """A `SKILL.md`: its file name, then its frontmatter, whose fields are `_SKILL`."""
    findings = []
    if prompt.path and prompt.path.name != "SKILL.md":
        findings.append(Finding(f"the file is named {prompt.path.name}, not SKILL.md"))
    return findings + _frontmatter_findings(prompt, _SKILL)


def anthropic_agent(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """A subagent's file: a name ending in `.md`, then its frontmatter, whose fields are `_AGENT`."""
    findings = []
    if prompt.path and not prompt.path.name.endswith(".md"):
        findings.append(Finding(f"the file is named {prompt.path.name}, which does not end in .md"))
    return findings + _frontmatter_findings(prompt, _AGENT)


def anthropic_claude(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """A `CLAUDE.md`: a name Claude Code loads, and a size it does not skip."""
    findings = []
    if prompt.path and prompt.path.name not in _CLAUDE_FILES:
        findings.append(Finding(f"the file is named {prompt.path.name}, not {' or '.join(_CLAUDE_FILES)}"))
    if (size := len(prompt.text.encode(errors="surrogatepass"))) > _MAX_BYTES:
        findings.append(Finding(f"{size} bytes as UTF-8, above the maximum of {_MAX_BYTES}, 4 MiB"))
    return findings


def _not_json(constant: str) -> NoReturn:
    raise ValueError(f"{constant} is not a JSON value")


def json_text(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    """A JSON text: one value, as RFC 8259 has it, which holds neither `NaN` nor `Infinity`
    nor a byte order mark before it. One finding at most, located where the parser stops."""
    if prompt.text.startswith("\ufeff"):
        return [Finding("starts with a byte order mark, which JSON forbids")]
    try:
        json.loads(prompt.text, parse_int=str, parse_constant=_not_json)  # str: a number of any length is JSON
    except json.JSONDecodeError as e:
        return [Finding(f"{e.msg}: column {e.colno}", e.lineno)]
    except ValueError as e:  # from _not_json
        return [Finding(str(e))]
    except RecursionError:
        return [Finding("nested too deep for Python to read")]
    return []


CHECKS: dict[str, CheckFunction] = {
    "anthropic-skill": anthropic_skill, "anthropic-agent": anthropic_agent, "anthropic-claude": anthropic_claude,
    "json": json_text,
}
