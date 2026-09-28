"""`run_check` on the two formats, per specs/static-checking.md, section Format.

Each table row lists the findings expected, one tuple per finding: the words its message holds,
and `Not(word)` for one it must not hold, as a length finding must not hold the value."""

from pathlib import Path

import pytest
from conftest import Project

from skilleval.static import CheckResult, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check

NAME = "name: my-skill\n"
DESCRIPTION = "description: Does a thing.\n"
SIX = "license: MIT\ncompatibility: Requires git.\nmetadata: {author: me, version: '1.0'}\nallowed-tools: Read Grep\n"
CLAUDE_CODE = """\
when_to_use: When refactoring.
argument-hint: "[file]"
arguments: [file, mode]
disable-model-invocation: true
user-invocable: false
disallowed-tools: [Bash]
model: claude-sonnet-5
effort: high
context: fork
agent: Explore
background: no
hooks: {PreToolUse: [{matcher: Bash}]}
paths: "src/**/*.py"
shell: bash
"""
STRINGS = ["license", "when_to_use", "argument-hint", "model", "agent"]
LISTS = ["allowed-tools", "disallowed-tools", "arguments", "paths"]
BOOLEANS = ["disable-model-invocation", "user-invocable", "background"]
# the quoted and mixed-case ones reach the check as strings, not YAML booleans
SPELLINGS = ["true", "No", "ON", "1", "0", "'true'", "'1'", "tRuE", "fAlSe", "yEs", "nO", "oN", "oFf"]
MIB4 = 4 * 2**20


class Not(str):
    """A word the message must not hold."""


def skill(fields: str, body: str = "Body.\n") -> str:
    return f"---\n{fields}---\n{body}"


def every(fields: list[str], value: str) -> str:
    return "".join(f"{field}: {value}\n" for field in fields)


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


@pytest.mark.parametrize("text, named", [
    pytest.param(skill(NAME + DESCRIPTION), [], id="a frontmatter"),
    pytest.param(f"---\n{NAME}{DESCRIPTION}---", [], id="closed on the last line"),
    pytest.param(skill(NAME + DESCRIPTION, "<example>\n---\n" + "line\n" * 600), [], id="a free body, --- included"),
    pytest.param("Just a body.\n", [()], id="no frontmatter"),
    pytest.param("", [()], id="empty"),
    pytest.param("\n---\n" + NAME + DESCRIPTION + "---\n", [()], id="--- not on the first line"),
    pytest.param("----\n" + NAME + DESCRIPTION + "---\n", [()], id="---- does not open it"),
    pytest.param("---\n" + NAME + DESCRIPTION + "----\n", [()], id="---- does not close it"),
    pytest.param("---\nname: My_Skill\nversion: 1\n", [()], id="never closed"),
    pytest.param(skill("name: [unclosed\nversion: 1\n"), [()], id="not YAML"),
    pytest.param(skill("license: 2024-99-99\n"), [()], id="a date that does not exist"),
    pytest.param(skill("metadata: " + "[" * 3000 + "]" * 3000 + "\n"), [()], id="nested too deep"),
    pytest.param(skill("- name: My_Skill\n- version: 1\n"), [()], id="a list"),
    pytest.param(skill(""), [()], id="empty frontmatter"),
    pytest.param(skill("just words\n"), [()], id="a string"),
])
def test_skill_frontmatter_opens_the_file_and_is_a_mapping_else_nothing_below_is_checked(
    text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-skill", Prompt(text)), named)


@pytest.mark.parametrize("fields, named", [
    pytest.param(NAME + DESCRIPTION, [], id="name and description"),
    pytest.param(NAME + DESCRIPTION + SIX, [], id="the six fields of the specification"),
    pytest.param(NAME + DESCRIPTION + CLAUDE_CODE, [], id="the fields Claude Code adds"),
    pytest.param(NAME + DESCRIPTION + "version: 1\n", [("version",)], id="an unknown field"),
    pytest.param(NAME + DESCRIPTION + "version: 1\nauthor: me\n", [("version",), ("author",)], id="one finding per unknown field"),
    pytest.param(NAME + DESCRIPTION + "when-to-use: Always.\n", [("when-to-use",)], id="when-to-use is not when_to_use"),
    pytest.param(DESCRIPTION, [("name",)], id="no name"),
    pytest.param(NAME, [("description",)], id="no description"),
    pytest.param("license: MIT\n", [("name",), ("description",)], id="neither"),
    pytest.param(DESCRIPTION + "version: 1\n", [("name",), ("version",)], id="no name and an unknown field"),
])
def test_skill_fields_are_documented_ones_with_name_and_description_there(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-skill", Prompt(skill(fields))), named)


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
    assert_findings(check("anthropic-skill", Prompt(skill(f"name: {name}\n" + DESCRIPTION))), named)


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
    assert_findings(check("anthropic-skill", Prompt(skill(NAME + f"description: {description}\n"))), named)


@pytest.mark.parametrize("fields, named", [
    pytest.param("compatibility: x\n", [], id="compatibility of 1 character"),
    pytest.param(f"compatibility: {'é' * 500}\n", [], id="compatibility of 500 characters"),
    pytest.param("compatibility: ''\n", [("compatibility",)], id="empty compatibility"),
    pytest.param(f"compatibility: {'x' * 501}\n", [("compatibility", Not("x" * 501))], id="compatibility of 501 characters"),
    pytest.param("compatibility: 42\n", [("compatibility", "42")], id="compatibility not a string"),
    pytest.param("license:\n", [("license",)], id="license without a value"),
    pytest.param(every(STRINGS, "[a, b]"), [(field,) for field in STRINGS], id="string fields given a list"),
    pytest.param("metadata: text\n", [("metadata", "text")], id="metadata not a mapping"),
    pytest.param("metadata: {version: 1.0}\n", [("metadata",)], id="metadata with a value not a string"),
    pytest.param("metadata: {1: one}\n", [("metadata",)], id="metadata with a key not a string"),
    pytest.param("hooks: {}\n", [], id="hooks a mapping"),
    pytest.param("hooks: [a]\n", [("hooks",)], id="hooks not a mapping"),
    pytest.param(every(LISTS, "Read"), [], id="list fields given a string"),
    pytest.param(every(LISTS, "[Read, Grep]"), [], id="list fields given a list of strings"),
    pytest.param(every(LISTS, "3"), [(field, "3") for field in LISTS], id="list fields given a number"),
    pytest.param(every(LISTS, "[Read, 3]"), [(field,) for field in LISTS], id="list fields given a list holding a number"),
    pytest.param(every(LISTS, "{a: b}"), [(field,) for field in LISTS], id="list fields given a mapping"),
])
def test_skill_other_field_has_the_type_of_its_row_and_compatibility_its_length(
    fields: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-skill", Prompt(skill(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("fields, named", [
    *[pytest.param(every(BOOLEANS, value), [], id=f"booleans {value}") for value in SPELLINGS],
    pytest.param(every(BOOLEANS, "maybe"), [(field, "maybe") for field in BOOLEANS], id="booleans maybe"),
    pytest.param(every(BOOLEANS, "2"), [(field, "2") for field in BOOLEANS], id="booleans 2"),
    pytest.param(every(BOOLEANS, "[true]"), [(field,) for field in BOOLEANS], id="booleans given a list"),
    *[pytest.param(f"effort: {value}\n", [], id=f"effort {value}") for value in ["low", "medium", "high", "xhigh", "max"]],
    pytest.param("effort: extreme\n", [("effort", "extreme")], id="effort extreme"),
    pytest.param("effort: High\n", [("effort", "High")], id="effort High, as written"),
    pytest.param("effort: 3\n", [("effort", "3")], id="effort not a string"),
    pytest.param("context: inline\n", [("context", "inline")], id="context not fork"),
    pytest.param("shell: powershell\n", [], id="shell powershell"),
    pytest.param("shell: zsh\n", [("shell", "zsh")], id="shell zsh"),
])
def test_skill_booleans_and_enumerations_take_one_of_their_values(fields: str, named: list[tuple[str, ...]]) -> None:
    assert_findings(check("anthropic-skill", Prompt(skill(NAME + DESCRIPTION + fields))), named)


@pytest.mark.parametrize("path, text, named", [
    pytest.param("skills/my-skill/SKILL.md", skill(NAME + DESCRIPTION), [], id="SKILL.md in a directory of its name"),
    pytest.param(None, skill(NAME + DESCRIPTION), [], id="an inline prompt has no file or directory"),
    pytest.param("skills/my-skill/README.md", skill(NAME + DESCRIPTION), [("README.md",)], id="another file name"),
    pytest.param("skills/my-skill/skill.md", skill(NAME + DESCRIPTION), [("skill.md",)], id="skill.md in lowercase"),
    pytest.param("skills/other/SKILL.md", skill(NAME + DESCRIPTION), [("name", "my-skill")], id="a directory of another name"),
    pytest.param("skills/My-Skill/SKILL.md", skill(NAME + DESCRIPTION), [("name", "my-skill")], id="a directory of another case"),
    pytest.param("skills/other/notes.md", skill(NAME + DESCRIPTION), [("notes.md",), ("name", "my-skill")], id="both"),
    pytest.param("skills/my-skill/SKILL.md", skill(DESCRIPTION), [("name",)], id="no name to compare with the directory"),
    pytest.param("skills/my-skill/README.md", "No frontmatter.\n", [("README.md",), ()], id="a file name checked without frontmatter"),
    pytest.param("skills/my-skill/README.md", skill("name: [unclosed\n"), [("README.md",), ()], id="a file name checked with no YAML"),
    pytest.param("skills/my-skill/README.md", skill("- a\n"), [("README.md",), ()], id="a file name checked with no mapping"),
])
def test_skill_file_is_named_skill_md_in_a_directory_named_after_the_skill(
    project: Project, path: str | None, text: str, named: list[tuple[str, ...]]
) -> None:
    assert_findings(check("anthropic-skill", file_prompt(project, path, text)), named)


def test_skill_directory_is_found_from_a_relative_path(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("my-skill/SKILL.md")
    monkeypatch.chdir(project.root / "my-skill")
    assert_findings(check("anthropic-skill", Prompt(skill(NAME + DESCRIPTION), Path("SKILL.md"))), [])


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
