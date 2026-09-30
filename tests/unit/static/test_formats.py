"""`run_check` on the four formats, per specs/static-checking.md, section Format.

Each table row lists the findings expected, one tuple per finding: the words its message holds,
and `Not(word)` for one it must not hold, as a length finding must not hold the value. What a
skill and a subagent share is one table, run on both formats; for a type both have, a table
names the fields of each format."""

from pathlib import Path

import pytest
from conftest import Project

from skilleval.static import CheckResult, Finding, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check

FORMATS = ["anthropic-skill", "anthropic-agent"]
NAME = "name: reviewer\n"
DESCRIPTION = "description: Does a thing.\n"
BOTH = "model: claude-sonnet-5\neffort: high\nbackground: no\nhooks: {PreToolUse: [{matcher: Bash}]}\n"
SIX = "license: MIT\ncompatibility: Requires git.\nmetadata: {author: me, version: '1.0'}\nallowed-tools: Read Grep\n"
CLAUDE_CODE = """\
when_to_use: When refactoring.
argument-hint: "[file]"
arguments: [file, mode]
disable-model-invocation: true
user-invocable: false
disallowed-tools: [Bash]
context: fork
agent: Explore
paths: "src/**/*.py"
shell: bash
"""
AGENT = """\
initialPrompt: Review the diff.
tools: Read, Grep
disallowedTools: [Bash]
skills: [api-conventions]
mcpServers: [github, {slack: {command: slack-mcp}}]
experimental: {cacheTtl: 1h}
maxTurns: 20
omitClaudeMd: true
permissionMode: plan
memory: project
isolation: worktree
color: purple
"""
STRINGS = {
    "anthropic-skill": ["license", "when_to_use", "argument-hint", "model", "agent"],
    "anthropic-agent": ["model", "initialPrompt"],
}
LISTS = {
    "anthropic-skill": ["allowed-tools", "disallowed-tools", "arguments", "paths"],
    "anthropic-agent": ["tools", "disallowedTools", "skills"],
}
MAPPINGS = {"anthropic-skill": ["hooks"], "anthropic-agent": ["hooks", "experimental"]}
BOOLEANS = {
    "anthropic-skill": ["disable-model-invocation", "user-invocable", "background"],
    "anthropic-agent": ["background", "omitClaudeMd"],
}
EFFORT = dict.fromkeys(FORMATS, ["effort"])
ONE_OF = {
    "permissionMode": ["default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"],
    "memory": ["user", "project", "local"],
    "isolation": ["worktree"],
    "color": ["red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"],
}
# the quoted and mixed-case ones reach the check as strings, not YAML booleans
SPELLINGS = ["true", "No", "ON", "1", "0", "'true'", "'1'", "tRuE", "fAlSe", "yEs", "nO", "oN", "oFf"]
MIB4 = 4 * 2**20


class Not(str):
    """A word the message must not hold."""


def document(fields: str, body: str = "Body.\n") -> str:
    return f"---\n{fields}---\n{body}"


def every(fields: list[str], value: str) -> str:
    return "".join(f"{field}: {value}\n" for field in fields)


def names(fields: str) -> list[str]:
    """The fields written, one a line."""
    return [line.partition(":")[0] for line in fields.splitlines()]


def file_prompt(project: Project, path: str | None, text: str) -> Prompt:
    """The text written at `path`, or inline when there is none."""
    return Prompt(text, project.write(path, text)) if path else Prompt(text)


def check(name: str, prompt: Prompt) -> CheckResult:
    return run_check(Check(name, {}, "error"), prompt)


def assert_findings(result: CheckResult, named: list[tuple[str, ...]]) -> None:
    assert result.status == ("failed" if named else "passed")
    assert len(result.findings) == len(named)
    for words in named:
        assert any(all((w not in f.message) if isinstance(w, Not) else (w in f.message) for w in words)
                   for f in result.findings), words
    assert all(f.line is None for f in result.findings)


# A skill and a subagent: what the two formats share


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize("text, named", [
    pytest.param(document(NAME + DESCRIPTION), [], id="a frontmatter"),
    pytest.param(f"---\n{NAME}{DESCRIPTION}---", [], id="closed on the last line"),
    pytest.param(document(NAME + DESCRIPTION, ""), [], id="an empty body"),
    pytest.param(document(NAME + DESCRIPTION, "<example>\n---\n" + "line\n" * 600), [], id="a free body, --- included"),
    pytest.param("Just a body.\n", [()], id="no frontmatter"),
    pytest.param("", [()], id="empty"),
    pytest.param("\n---\n" + NAME + DESCRIPTION + "---\n", [()], id="--- not on the first line"),
    pytest.param("----\n" + NAME + DESCRIPTION + "---\n", [()], id="---- does not open it"),
    pytest.param("---\n" + NAME + DESCRIPTION + "----\n", [()], id="---- does not close it"),
    pytest.param("---\nname: reviewer\nversion: 1\n", [()], id="never closed"),
    pytest.param(document("name: [unclosed\nversion: 1\n"), [()], id="not YAML"),
    pytest.param(document("model: 2024-99-99\n"), [()], id="a date that does not exist"),
    pytest.param(document("hooks: " + "[" * 3000 + "]" * 3000 + "\n"), [()], id="nested too deep"),
    pytest.param(document("- name: reviewer\n- version: 1\n"), [()], id="a list"),
    pytest.param(document(""), [()], id="empty frontmatter"),
    pytest.param(document("just words\n"), [()], id="a string"),
])
def test_frontmatter_opens_the_file_and_is_a_mapping_else_nothing_below_is_checked(
    format: str, text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check(format, Prompt(text)), named)


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize("fields, named", [
    pytest.param(NAME + DESCRIPTION, [], id="name and description"),
    pytest.param(NAME + DESCRIPTION + "version: 1\n", [("version",)], id="an unknown field"),
    pytest.param(NAME + DESCRIPTION + "version: 1\nauthor: me\n", [("version",), ("author",)], id="one finding per unknown field"),
    pytest.param(DESCRIPTION, [("name",)], id="no name"),
    pytest.param(NAME, [("description",)], id="no description"),
    pytest.param("model: sonnet\n", [("name",), ("description",)], id="neither"),
    pytest.param(DESCRIPTION + "version: 1\n", [("name",), ("version",)], id="no name and an unknown field"),
])
def test_fields_are_documented_ones_with_name_and_description_there(
    format: str, fields: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check(format, Prompt(document(fields))), named)


@pytest.mark.parametrize("format, path", [
    pytest.param("anthropic-skill", "skills/reviewer/README.md", id="anthropic-skill"),
    pytest.param("anthropic-agent", "agents/reviewer.txt", id="anthropic-agent"),
])
@pytest.mark.parametrize("text", [
    pytest.param("No frontmatter.\n", id="without frontmatter"),
    pytest.param(document("name: [unclosed\n"), id="with no YAML"),
    pytest.param(document("- a\n"), id="with no mapping"),
])
def test_file_name_is_checked_whatever_the_frontmatter(project: Project, format: str, path: str, text: str) -> None:
    assert_findings(check(format, file_prompt(project, path, text)), [(Path(path).name,), ()])


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize("fields, value, held", [
    pytest.param(STRINGS, "''", None, id="string fields given an empty string"),
    pytest.param(STRINGS, "[a, b]", (), id="string fields given a list"),
    pytest.param(STRINGS, "42", ("42",), id="string fields given a number"),
    pytest.param(STRINGS, "", (), id="string fields without a value"),
    pytest.param(MAPPINGS, "{}", None, id="mapping fields given a mapping"),
    pytest.param(MAPPINGS, "[a]", (), id="mapping fields given a list"),
    pytest.param(MAPPINGS, "text", ("text",), id="mapping fields given a string"),
    pytest.param(LISTS, "Read", None, id="list fields given a string"),
    pytest.param(LISTS, "[Read, Grep]", None, id="list fields given a list of strings"),
    pytest.param(LISTS, "3", ("3",), id="list fields given a number"),
    pytest.param(LISTS, "[Read, 3]", (), id="list fields given a list holding a number"),
    pytest.param(LISTS, "{a: b}", (), id="list fields given a mapping"),
    *[pytest.param(BOOLEANS, value, None, id=f"booleans {value}") for value in SPELLINGS],
    pytest.param(BOOLEANS, "maybe", ("maybe",), id="booleans maybe"),
    pytest.param(BOOLEANS, "2", ("2",), id="booleans 2"),
    pytest.param(BOOLEANS, "[true]", (), id="booleans given a list"),
    *[pytest.param(EFFORT, value, None, id=f"effort {value}") for value in ["low", "medium", "high", "xhigh", "max"]],
    pytest.param(EFFORT, "extreme", ("extreme",), id="effort extreme"),
    pytest.param(EFFORT, "High", ("High",), id="effort High, as written"),
    pytest.param(EFFORT, "3", ("3",), id="effort not a string"),
])
def test_field_takes_what_its_type_allows_in_both_formats(
    format: str, fields: dict[str, list[str]], value: str, held: tuple[str, ...] | None
) -> None:
    """Each field of the format is given `value`: one finding a field, holding its name and `held`, none when that is None."""
    named = [] if held is None else [(field, *held) for field in fields[format]]
    assert_findings(check(format, Prompt(document(NAME + DESCRIPTION + every(fields[format], value)))), named)


# A skill


@pytest.mark.parametrize("fields, named", [
    pytest.param(SIX, [], id="the six fields of the specification"),
    pytest.param(CLAUDE_CODE + BOTH, [], id="the fields Claude Code adds"),
    pytest.param("when-to-use: Always.\n", [("when-to-use",)], id="when-to-use is not when_to_use"),
    pytest.param(AGENT, [(field,) for field in names(AGENT)], id="the fields of a subagent alone"),
])
def test_skill_fields_are_those_of_the_specification_and_of_claude_code(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-skill", Prompt(document(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("name, named", [
    pytest.param("a" * 64, [], id="64 characters"),
    pytest.param("a1-b2-c3", [], id="digits and single hyphens"),
    pytest.param("a" * 65, [("name", Not("a" * 65))], id="65 characters"),
    pytest.param("My-skill", [("name", "My-skill")], id="uppercase"),
    pytest.param("my_skill", [("name", "my_skill")], id="an underscore"),
    pytest.param("café", [("name", "café")], id="a letter outside a-z"),
    pytest.param('"my-skill\\n"', [("name",)], id="a trailing newline"),
    pytest.param("''", [("name",)], id="empty"),
    pytest.param("-my-skill", [("name", "-my-skill")], id="a hyphen first"),
    pytest.param("my-skill-", [("name", "my-skill-")], id="a hyphen last"),
    pytest.param("my--skill", [("name", "my--skill")], id="two hyphens in a row"),
    pytest.param("My--skill", [("name", "My--skill")], id="uppercase and two hyphens: one clause, once"),
    pytest.param("claudette", [("name", "claudette")], id="holding claude"),
    pytest.param("myanthropic", [("name", "myanthropic")], id="holding anthropic"),
    pytest.param("Claude-helper", [("name", "Claude-helper")], id="Claude is uppercase, not reserved"),
    pytest.param(f"{'a' * 60}-claude", [("name", Not(f"{'a' * 60}-claude")), ("name", f"{'a' * 60}-claude")],
                 id="too long and holding claude"),
    pytest.param("123", [("name", "123")], id="not a string"),
    pytest.param("", [("name",)], id="without a value"),
])
def test_skill_name_is_a_short_lowercase_hyphenated_unreserved_string(name: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-skill", Prompt(document(f"name: {name}\n" + DESCRIPTION))), named)


@pytest.mark.parametrize("description, named", [
    pytest.param("é" * 1024, [], id="1024 characters"),
    pytest.param("x" * 1025, [("description", Not("x" * 1025))], id="1025 characters"),
    pytest.param("''", [("description",)], id="empty"),
    pytest.param("'   '", [("description",)], id="blank"),
    pytest.param("'a < b'", [("description", "a < b")], id="with <"),
    pytest.param("'a > b'", [("description", "a > b")], id="with >"),
    pytest.param("'a <b> c'", [("description", "a <b> c")], id="with < and >: one clause, once"),
    pytest.param(f"'{'x' * 1025}<'", [("description", Not(f"{'x' * 1025}<")), ("description", f"{'x' * 1025}<")],
                 id="too long and with <"),
    pytest.param("[a, b]", [("description",)], id="not a string"),
])
def test_skill_description_is_a_string_neither_blank_nor_long_nor_holding_angle_brackets(
    description: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-skill", Prompt(document(NAME + f"description: {description}\n"))), named)


@pytest.mark.parametrize("fields, named", [
    pytest.param("compatibility: x\n", [], id="compatibility of 1 character"),
    pytest.param(f"compatibility: {'é' * 500}\n", [], id="compatibility of 500 characters"),
    pytest.param("compatibility: ''\n", [("compatibility",)], id="empty compatibility"),
    pytest.param(f"compatibility: {'x' * 501}\n", [("compatibility", Not("x" * 501))], id="compatibility of 501 characters"),
    pytest.param("compatibility: 42\n", [("compatibility", "42")], id="compatibility not a string"),
    pytest.param("metadata: text\n", [("metadata", "text")], id="metadata not a mapping"),
    pytest.param("metadata: {version: 1.0}\n", [("metadata",)], id="metadata with a value not a string"),
    pytest.param("metadata: {1: one}\n", [("metadata",)], id="metadata with a key not a string"),
    pytest.param("context: inline\n", [("context", "inline")], id="context not fork"),
    pytest.param("shell: powershell\n", [], id="shell powershell"),
    pytest.param("shell: zsh\n", [("shell", "zsh")], id="shell zsh"),
])
def test_skill_compatibility_metadata_context_and_shell_follow_their_rules(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-skill", Prompt(document(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("path, text, named", [
    pytest.param("skills/reviewer/SKILL.md", document(NAME + DESCRIPTION), [], id="SKILL.md in a directory of its name"),
    pytest.param(None, document(NAME + DESCRIPTION), [], id="an inline prompt has no file or directory"),
    pytest.param("skills/reviewer/README.md", document(NAME + DESCRIPTION), [("README.md",)], id="another file name"),
    pytest.param("skills/reviewer/skill.md", document(NAME + DESCRIPTION), [("skill.md",)], id="skill.md in lowercase"),
    pytest.param("skills/other/SKILL.md", document(NAME + DESCRIPTION), [("name", "reviewer")], id="a directory of another name"),
    pytest.param("skills/Reviewer/SKILL.md", document(NAME + DESCRIPTION), [("name", "reviewer")], id="a directory of another case"),
    pytest.param("skills/other/notes.md", document(NAME + DESCRIPTION), [("notes.md",), ("name", "reviewer")], id="both"),
    pytest.param("skills/reviewer/SKILL.md", document(DESCRIPTION), [("name",)], id="no name to compare with the directory"),
])
def test_skill_file_is_named_skill_md_in_a_directory_named_after_the_skill(
    project: Project, path: str | None, text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-skill", file_prompt(project, path, text)), named)


def test_skill_directory_is_found_from_a_relative_path(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("reviewer/SKILL.md")
    monkeypatch.chdir(project.root / "reviewer")
    assert_findings(check("anthropic-skill", Prompt(document(NAME + DESCRIPTION), Path("SKILL.md"))), [])


# A subagent


@pytest.mark.parametrize("fields, named", [
    pytest.param(AGENT + BOTH, [], id="every field of the table"),
    pytest.param("max-turns: 20\n", [("max-turns",)], id="max-turns is not maxTurns"),
    pytest.param("max_turns: 20\n", [("max_turns",)], id="max_turns is not maxTurns"),
    pytest.param("maxturns: 20\n", [("maxturns",)], id="maxturns is not maxTurns"),
    pytest.param("cacheTtl: 1h\n", [("cacheTtl",)], id="cacheTtl outside experimental"),
    pytest.param(SIX + CLAUDE_CODE, [(field,) for field in names(SIX + CLAUDE_CODE)], id="the fields of a skill alone"),
])
def test_agent_fields_are_those_of_its_table_spelt_as_there(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-agent", Prompt(document(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("name, named", [
    pytest.param("code-reviewer", [], id="a hyphen inside"),
    pytest.param("reviewer-", [], id="a hyphen last"),
    pytest.param("code--reviewer", [], id="two hyphens in a row"),
    pytest.param("Code_Reviewer 2 é", [], id="a capital, an underscore, a space and a letter outside a-z"),
    pytest.param("claude-anthropic", [], id="holding claude and anthropic"),
    pytest.param("a" * 65, [], id="65 characters"),
    pytest.param("-reviewer", [("name", "-reviewer")], id="a hyphen first"),
    pytest.param("plugin:reviewer", [("name", "plugin:reviewer")], id="a : inside"),
    pytest.param("'reviewer:'", [("name", "reviewer:")], id="a : last"),
    pytest.param("a:b:c", [("name", "a:b:c")], id="two : give one clause, once"),
    pytest.param("-plugin:reviewer", [("name", "-plugin:reviewer"), ("name", "-plugin:reviewer")],
                 id="a hyphen first and a : give two clauses"),
    pytest.param("''", [("name",)], id="empty"),
    pytest.param("'   '", [("name",)], id="blank"),
    pytest.param("-1", [("name", "-1")], id="a number, its hyphen first not a second finding"),
    pytest.param("[a, b]", [("name",)], id="a list"),
    pytest.param("", [("name",)], id="without a value"),
])
def test_agent_name_is_a_string_not_blank_without_a_colon_or_a_hyphen_first(name: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-agent", Prompt(document(f"name: {name}\n" + DESCRIPTION))), named)


@pytest.mark.parametrize("description, named", [
    pytest.param("x", [], id="1 character"),
    pytest.param("x" * 1025, [], id="1025 characters"),
    pytest.param("'Use for <code> review.'", [], id="with < and >"),
    pytest.param("''", [("description",)], id="empty"),
    pytest.param("'   '", [("description",)], id="blank"),
    pytest.param("42", [("description", "42")], id="a number"),
    pytest.param("[a, b]", [("description",)], id="a list"),
    pytest.param("", [("description",)], id="without a value"),
])
def test_agent_description_is_a_string_not_blank(description: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-agent", Prompt(document(NAME + f"description: {description}\n"))), named)


@pytest.mark.parametrize("fields, named", [
    pytest.param("mcpServers: [github]\n", [], id="mcpServers naming a server"),
    pytest.param("mcpServers: [{slack: {command: slack-mcp}}]\n", [], id="mcpServers defining a server"),
    pytest.param("mcpServers: []\n", [], id="mcpServers empty"),
    pytest.param("mcpServers: github\n", [("mcpServers", "github")], id="mcpServers a string"),
    pytest.param("mcpServers: {slack: {command: slack-mcp}}\n", [("mcpServers",)], id="mcpServers a mapping"),
    pytest.param("mcpServers: [github, 3]\n", [("mcpServers",)], id="mcpServers holding a number"),
    pytest.param("mcpServers: [[github]]\n", [("mcpServers",)], id="mcpServers holding a list"),
    pytest.param("mcpServers: [~]\n", [("mcpServers",)], id="mcpServers holding null, as a bare - gives"),
    pytest.param("mcpServers: [3, [github], true]\n", [("mcpServers",)], id="mcpServers holding three of them: one clause, once"),
    pytest.param("experimental: {retries: 3}\n", [], id="experimental with a value not a string"),
    pytest.param("maxTurns: 1\n", [], id="maxTurns 1"),
    pytest.param("maxTurns: 200\n", [], id="maxTurns 200, no upper bound"),
    pytest.param("maxTurns: 0\n", [("maxTurns", "0")], id="maxTurns 0"),
    pytest.param("maxTurns: -1\n", [("maxTurns", "-1")], id="maxTurns -1"),
    pytest.param("maxTurns: true\n", [("maxTurns",)], id="maxTurns true, a YAML boolean and not 1"),
    pytest.param("maxTurns: 1.5\n", [("maxTurns", "1.5")], id="maxTurns 1.5, not a whole number"),
    pytest.param("maxTurns: 2.0\n", [("maxTurns", "2.0")], id="maxTurns 2.0, whole and not an integer"),
    pytest.param("maxTurns: '3'\n", [("maxTurns", "3")], id="maxTurns '3', a string"),
    pytest.param("maxTurns: 0.5\n", [("maxTurns", "0.5")], id="maxTurns 0.5, its type alone and not its bound"),
    pytest.param("maxTurns: [1]\n", [("maxTurns",)], id="maxTurns a list"),
    pytest.param("maxTurns:\n", [("maxTurns",)], id="maxTurns without a value"),
    # enumerations take one of their values as written
    *[pytest.param(f"{field}: {value}\n", [], id=f"{field} {value}") for field, values in ONE_OF.items() for value in values],
    pytest.param("permissionMode: ask\n", [("permissionMode", "ask")], id="permissionMode ask"),
    pytest.param("permissionMode: acceptedits\n", [("permissionMode", "acceptedits")], id="permissionMode acceptedits, as written"),
    pytest.param("memory: global\n", [("memory", "global")], id="memory global"),
    pytest.param("isolation: container\n", [("isolation", "container")], id="isolation container"),
    pytest.param("color: magenta\n", [("color", "magenta")], id="color magenta"),
    pytest.param("memory: User\n", [("memory", "User")], id="memory User, as written"),
    pytest.param("isolation: Worktree\n", [("isolation", "Worktree")], id="isolation Worktree, as written"),
    pytest.param("color: Red\n", [("color", "Red")], id="color Red, as written"),
    pytest.param(every(list(ONE_OF), "3"), [(field, "3") for field in ONE_OF], id="enumerations given a number"),
    pytest.param(every(list(ONE_OF), "[a]"), [(field,) for field in ONE_OF], id="enumerations given a list"),
])
def test_agent_mcp_servers_experimental_max_turns_and_enumerations_follow_their_rules(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-agent", Prompt(document(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("path, text, named", [
    pytest.param("agents/reviewer.md", document(NAME + DESCRIPTION), [], id="a Markdown file named after the subagent"),
    pytest.param("agents/other.md", document(NAME + DESCRIPTION), [], id="a file name that is not the name"),
    pytest.param(".claude/agents/review/reviewer.md", document(NAME + DESCRIPTION), [], id="below an agents directory"),
    pytest.param("notes/reviewer.md", document(NAME + DESCRIPTION), [], id="outside an agents directory"),
    pytest.param(None, document(NAME + DESCRIPTION), [], id="an inline prompt has no file"),
    pytest.param("agents/reviewer.txt", document(NAME + DESCRIPTION), [("reviewer.txt",)], id="another suffix"),
    pytest.param("agents/reviewer.MD", document(NAME + DESCRIPTION), [("reviewer.MD",)], id=".MD in capitals"),
    pytest.param("agents/reviewer.md.bak", document(NAME + DESCRIPTION), [("reviewer.md.bak",)], id=".md before the suffix"),
    pytest.param("agents/reviewermd", document(NAME + DESCRIPTION), [("reviewermd",)], id="md without its dot"),
    pytest.param("agents/reviewer", document(NAME + DESCRIPTION), [("reviewer",)], id="no suffix"),
    pytest.param("agents/reviewer.txt", document(NAME), [("reviewer.txt",), ("description",)], id="the file and a field"),
])
def test_agent_file_name_ends_in_md_and_is_free_otherwise(
    project: Project, path: str | None, text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-agent", file_prompt(project, path, text)), named)


# A CLAUDE.md


@pytest.mark.parametrize("path, text, named", [
    pytest.param(None, "# Rules\n", [], id="an inline prompt has no file"),
    pytest.param("CLAUDE.md", "", [], id="CLAUDE.md"),
    pytest.param("CLAUDE.local.md", "Local rules.\n", [], id="CLAUDE.local.md"),
    pytest.param("sub/dir/CLAUDE.md", "Rules.\n", [], id="CLAUDE.md in a subdirectory"),
    pytest.param("claude.md", "Rules.\n", [("claude.md",)], id="claude.md in lowercase"),
    pytest.param("AGENTS.md", "Rules.\n", [("AGENTS.md",)], id="AGENTS.md"),
    pytest.param("CLAUDE.other.md", "Rules.\n", [("CLAUDE.other.md",)], id="CLAUDE.other.md"),
    pytest.param("CLAUDE.md.bak", "Rules.\n", [("CLAUDE.md.bak",)], id="another suffix"),
    pytest.param(None, "---\nname: x\n---\nNo heading, and @missing/import.md.\n", [],
                 id="frontmatter, no heading and a missing import"),
    pytest.param(None, "a" * MIB4, [], id="4 MiB"),
    pytest.param(None, "a\ud800b", [], id="a lone surrogate"),
    pytest.param(None, "a" * (MIB4 + 1), [()], id="4 MiB and one byte"),
    pytest.param(None, "é" * (MIB4 // 2), [], id="4 MiB in two-byte characters"),
    pytest.param(None, "é" * (MIB4 // 2) + "a", [()], id="one byte more, far fewer characters"),
    pytest.param("claude.md", "a" * (MIB4 + 1), [("claude.md",), ()], id="misnamed and too large"),
])
def test_claude_md_is_named_as_claude_code_loads_it_and_at_most_4_mib(
    project: Project, path: str | None, text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-claude", file_prompt(project, path, text)), named)


# JSON


@pytest.mark.parametrize("text", [
    pytest.param('{"a": [1, -2.5e3, true, false, null, "\\u00e9"]}', id="an object of every kind of value"),
    pytest.param(' \n"text"\r\n\t', id="a string, whitespace around"),
    pytest.param("0", id="a number"),
    pytest.param("1" * 5000, id="a number of any length"),
    pytest.param("1e400", id="a number of any size"),
    pytest.param('{"a": 1, "a": 2}', id="duplicate names"),
    pytest.param("[" * 500 + "]" * 500, id="a nesting 500 deep"),
    pytest.param('["\ufeff"]', id="a byte order mark inside a string"),
])
def test_json_is_one_value_as_rfc_8259_has_it(text: str) -> None:
    assert check("json", Prompt(text)).status == "passed"


@pytest.mark.parametrize("text, message, line", [
    pytest.param("", "Expecting value: column 1", 1, id="empty"),
    pytest.param("  \n ", "Expecting value: column 2", 2, id="blank"),
    pytest.param('{"a": 1}\n{"b": 2}', "Extra data: column 1", 2, id="two values"),
    pytest.param('{\n  "a": 1\n  "b": 2\n}', "Expecting ',' delimiter: column 3", 3, id="a missing comma"),
    pytest.param("{'a': 1}", "Expecting property name enclosed in double quotes: column 2", 1, id="single quotes"),
    pytest.param("```json\n{}\n```", "Expecting value: column 1", 1, id="a code fence around it"),
    pytest.param("NaN", "NaN is not a JSON value", None, id="NaN"),
    pytest.param('{"a": [Infinity]}', "Infinity is not a JSON value", None, id="Infinity"),
    pytest.param("-Infinity", "-Infinity is not a JSON value", None, id="-Infinity"),
    pytest.param("\ufeff{}", "starts with a byte order mark, which JSON forbids", None, id="a byte order mark"),
    pytest.param(" \ufeff{}", "Expecting value: column 2", 1, id="a byte order mark after a space"),
    pytest.param("[" * 100_000 + "]" * 100_000, "nested too deep for Python to read", None, id="a nesting too deep for Python"),
])
def test_json_that_is_not_has_one_finding_located_where_the_parser_stops(text: str, message: str, line: int | None) -> None:
    result = check("json", Prompt(text))
    assert result.status == "failed"
    assert result.findings == (Finding(message, line),)
