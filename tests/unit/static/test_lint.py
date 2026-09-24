"""`run_check` on every lint and format check, per specs/static-checking.md."""

from pathlib import Path

import pytest
from conftest import Project

from skilleval.static import CHECKS, CheckResult, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check
from skilleval.testfile.checks import CONSTRAINTS, FORMATS, LINT

INVISIBLE = ["\ufeff", "\u00a0", "\u202f", "\u200b", "\u200c", "\u200d", "\u2060"]


def test_every_check_name_the_loader_accepts_has_a_function():
    # passes against the skeleton by design: it pins values that already exist
    assert set(CHECKS) == LINT | FORMATS | CONSTRAINTS


def run(name: str, prompt: Prompt, severity: str = "error") -> CheckResult:
    check = Check(name, {}, severity)
    result = run_check(check, prompt)
    assert result.check == check
    return result


def file_prompt(project: Project, rel: str, text: str, root: Path | None = None) -> Prompt:
    return Prompt(text, project.write(rel, text), root)


# chars


@pytest.mark.parametrize(
    ("char", "text", "line"),
    [(c, f"clean\nbad{c}here", 2) for c in INVISIBLE] + [("\ufeff", "\ufeffhello", 1)],
)
def test_chars_reports_each_invisible_codepoint_with_its_line(char: str, text: str, line: int) -> None:
    result = run("chars", Prompt(text))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [line]
    assert f"U+{ord(char):04X}" in result.findings[0].message


def test_chars_one_finding_per_occurrence() -> None:
    result = run("chars", Prompt("a\u00a0b\u00a0c\nd\n\u200be"))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1, 1, 3]


@pytest.mark.parametrize("text", [
    "",
    "plain ascii",
    "“smart” and ‘quotes’",
    "windows\r\nline endings\r\n",
    "\ta tab\tinside",
    "emoji \U0001f389 here",
    "accents café naïve",
])
def test_chars_passes_everything_else(text: str) -> None:
    result = run("chars", Prompt(text))
    assert result.status == "passed"
    assert result.findings == ()


# markdown_links


@pytest.mark.parametrize("target", ["b.md", "./b.md", "sub/c.md", "../top.md"])
def test_markdown_links_relative_target_that_exists_passes(project: Project, target: str) -> None:
    for existing in ("docs/b.md", "docs/sub/c.md", "top.md"):
        project.write(existing, "# Ok\n")
    result = run("markdown_links", file_prompt(project, "docs/a.md", f"see [x]({target})"))
    assert result.status == "passed"
    assert result.findings == ()


@pytest.mark.parametrize("link", ["[x](missing.md)", "![x](missing.md)"])
def test_markdown_links_missing_target_fails_with_the_link_line(project: Project, link: str) -> None:
    result = run("markdown_links", file_prompt(project, "a.md", f"intro\n\nsee {link}"))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [3]
    assert "missing.md" in result.findings[0].message


def test_markdown_links_missing_target_with_an_anchor_is_one_finding(project: Project) -> None:
    result = run("markdown_links", file_prompt(project, "a.md", "[x](missing.md#usage)"))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1]


@pytest.mark.parametrize(("anchor", "status"), [
    ("#my-heading", "passed"),
    ("#twice-1", "passed"),
    ("#nope", "failed"),
])
def test_markdown_links_anchor_must_match_a_github_slug_in_the_target(project: Project, anchor: str, status: str) -> None:
    project.write("b.md", "# My Heading\n\n# Twice\n\n# Twice\n")
    result = run("markdown_links", file_prompt(project, "a.md", f"[x](b.md{anchor})"))
    assert result.status == status
    assert [f.line for f in result.findings] == ([1] if status == "failed" else [])


@pytest.mark.parametrize(("anchor", "status"), [
    ("#setup", "passed"),
    ("#nope", "failed"),
])
def test_markdown_links_bare_anchor_checks_the_same_file(project: Project, anchor: str, status: str) -> None:
    result = run("markdown_links", file_prompt(project, "a.md", f"# Setup\n\n[x]({anchor})"))
    assert result.status == status
    assert [f.line for f in result.findings] == ([1] if status == "failed" else [])


@pytest.mark.parametrize("text", [
    "[x](https://nope.invalid/missing.md)",
    "[x](http://nope.invalid/missing.md#nope)",
    "no links at all",
    "",
])
def test_markdown_links_leaves_http_links_to_urls(project: Project, text: str) -> None:
    result = run("markdown_links", file_prompt(project, "a.md", text))
    assert result.status == "passed"
    assert result.findings == ()


def test_markdown_links_one_finding_per_broken_link(project: Project) -> None:
    project.write("b.md", "# Ok\n")
    text = "[a](missing.md) [b](b.md)\n[c](b.md#nope)"
    result = run("markdown_links", file_prompt(project, "a.md", text))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1, 2]


def test_markdown_links_slash_target_resolves_from_root(project: Project) -> None:
    project.write("README.md", "# Top\n")
    prompt = file_prompt(project, "docs/a.md", "[x](/README.md#top)", root=project.root)
    result = run("markdown_links", prompt)
    assert result.status == "passed"
    assert result.findings == ()


def test_markdown_links_slash_target_missing_from_root_fails(project: Project) -> None:
    prompt = file_prompt(project, "docs/a.md", "[x](/missing.md)", root=project.root)
    result = run("markdown_links", prompt)
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1]
    assert "/missing.md" in result.findings[0].message


def test_markdown_links_slash_target_without_root_is_a_finding(project: Project) -> None:
    project.write("README.md", "# Top\n")
    prompt = file_prompt(project, "docs/a.md", "intro\n[x](/README.md)", root=None)
    result = run("markdown_links", prompt)
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [2]
    assert "/README.md" in result.findings[0].message


# paths_exist


def test_paths_exist_passes_when_every_path_resolves_from_the_file_directory(project: Project) -> None:
    for existing in ("docs/b.md", "docs/sub/c.py", "top.md"):
        project.write(existing)
    text = "see ./b.md, `sub/c.py` and ../top.md"
    result = run("paths_exist", file_prompt(project, "docs/a.md", text))
    assert result.status == "passed"
    assert result.findings == ()
    assert result.detected == ("./b.md", "sub/c.py", "../top.md")


def test_paths_exist_missing_path_is_a_finding_with_its_line(project: Project) -> None:
    project.write("docs/b.md")
    text = "see ./b.md\nand ./missing.md"
    result = run("paths_exist", file_prompt(project, "docs/a.md", text))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [2]
    assert "./missing.md" in result.findings[0].message
    assert result.detected == ("./b.md", "./missing.md")


def test_paths_exist_absolute_path_is_taken_as_is(project: Project) -> None:
    existing = project.write("top.md")
    result = run("paths_exist", file_prompt(project, "docs/a.md", f"see {existing}"))
    assert result.status == "passed"
    assert result.detected == (str(existing),)


def test_paths_exist_directory_counts_as_existing(project: Project) -> None:
    project.write("docs/b.md")
    result = run("paths_exist", file_prompt(project, "a.md", "in the docs/ tree"))
    assert result.status == "passed"
    assert result.detected == ("docs/",)


def test_paths_exist_tilde_resolves_through_the_home_directory(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(project.root))
    monkeypatch.setenv("USERPROFILE", str(project.root))
    project.write("notes.md")
    result = run("paths_exist", file_prompt(project, "docs/a.md", "see ~/notes.md"))
    assert result.status == "passed"
    assert result.detected == ("~/notes.md",)


def test_paths_exist_skips_fenced_blocks(project: Project) -> None:
    result = run("paths_exist", file_prompt(project, "a.md", "```\nedit path/to/file.py\n```"))
    assert result.status == "passed"
    assert result.findings == ()
    assert result.detected == ()


def test_paths_exist_one_finding_per_missing_path(project: Project) -> None:
    text = "see ./x.md and ./y.md\nand ./z.md"
    result = run("paths_exist", file_prompt(project, "a.md", text))
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1, 1, 2]
    assert result.detected == ("./x.md", "./y.md", "./z.md")


# file-only lints on a text prompt


@pytest.mark.parametrize("name", ["markdown_links", "paths_exist"])
def test_file_only_lint_is_skipped_on_a_text_prompt(name: str) -> None:
    result = run(name, Prompt("see [x](./missing.md)"))
    assert result.status == "skipped"
    assert result.findings == ()


# format


@pytest.mark.parametrize("name", ["anthropic-skill", "anthropic-claude"])
def test_format_runs_nothing_and_passes(name: str) -> None:
    result = run(name, Prompt("anything at all"))
    assert result.status == "passed"
    assert result.findings == ()


# severity


@pytest.mark.parametrize(("text", "status"), [
    ("a\u00a0b", "warned"),
    ("a b", "passed"),
])
def test_warn_severity_on_a_lint(text: str, status: str) -> None:
    result = run("chars", Prompt(text), severity="warn")
    assert result.status == status
    assert [f.line for f in result.findings] == ([1] if status == "warned" else [])
