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


# chars: exactly seven codepoints, one finding per occurrence with its line and escaped codepoint


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


# markdown_links: the prompt is docs/a.md; docs/b.md (headings My Heading, Twice, Twice), docs/sub/c.md, top.md and README.md exist


@pytest.mark.parametrize(("text", "with_root", "findings"), [
    # relative targets resolve from the file's directory; images count like links
    ("see [x](b.md)", False, ()),
    ("see [x](./b.md)", False, ()),
    ("see [x](sub/c.md)", False, ()),
    ("see [x](../top.md)", False, ()),
    ("intro\n\nsee [x](missing.md)", False, ((3, "missing.md"),)),
    ("intro\n\nsee ![x](missing.md)", False, ((3, "missing.md"),)),
    ("[x](missing.md#usage)", False, ((1, "missing.md"),)),  # one finding, not one per anchor
    # anchors match a heading slug in the target, or in the same file when bare
    ("[x](b.md#my-heading)", False, ()),
    ("[x](b.md#twice-1)", False, ()),  # duplicate headings are numbered
    ("[x](b.md#nope)", False, ((1, "#nope"),)),
    ("# Setup\n\n[x](#setup)", False, ()),
    ("# Setup\n\n[x](#nope)", False, ((3, "#nope"),)),
    # http(s) links are left to urls
    ("[x](http://nope.invalid/missing.md#nope)", False, ()),
    ("", False, ()),
    ("[a](missing.md) [b](b.md)\n[c](b.md#nope)", False, ((1, "missing.md"), (2, "#nope"))),  # one finding per broken link
    # a / target resolves from the project root, and is a finding without one
    ("[x](/README.md#top)", True, ()),
    ("[x](/missing.md)", True, ((1, "/missing.md"),)),
    ("intro\n[x](/README.md)", False, ((2, "/README.md"),)),
])
def test_markdown_links_resolve_targets_and_anchors(
    project: Project, text: str, with_root: bool, findings: tuple[tuple[int, str], ...]
) -> None:
    project.write("docs/b.md", "# My Heading\n\n# Twice\n\n# Twice\n")
    project.write("docs/sub/c.md", "# Ok\n")
    project.write("top.md", "# Ok\n")
    project.write("README.md", "# Top\n")
    result = run("markdown_links", file_prompt(project, "docs/a.md", text, project.root if with_root else None))
    assert result.status == ("failed" if findings else "passed")
    assert [f.line for f in result.findings] == [line for line, _ in findings]
    for finding, (_, named) in zip(result.findings, findings, strict=True):
        assert named in finding.message


# paths_exist: the prompt is docs/a.md; docs/b.md and docs/sub/c.py exist, so does top.md


@pytest.mark.parametrize(("text", "findings", "detected"), [
    ("see ./b.md, `sub/c.py` and ../top.md", (), ("./b.md", "sub/c.py", "../top.md")),  # from the file's directory
    ("see ./b.md\nand ./missing.md", ((2, "./missing.md"),), ("./b.md", "./missing.md")),
    ("in the sub/ tree", (), ("sub/",)),  # a directory counts
    ("```\nedit path/to/file.py\n```", (), ()),  # fenced blocks are skipped
    ("see ./x.md and ./y.md\nand ./z.md", ((1, "./x.md"), (1, "./y.md"), (2, "./z.md")), ("./x.md", "./y.md", "./z.md")),
])
def test_paths_exist_resolves_every_path_outside_fences(
    project: Project, text: str, findings: tuple[tuple[int, str], ...], detected: tuple[str, ...]
) -> None:
    for existing in ("docs/b.md", "docs/sub/c.py", "top.md"):
        project.write(existing)
    result = run("paths_exist", file_prompt(project, "docs/a.md", text))
    assert result.status == ("failed" if findings else "passed")
    assert [f.line for f in result.findings] == [line for line, _ in findings]
    for finding, (_, named) in zip(result.findings, findings, strict=True):
        assert named in finding.message
    assert result.detected == detected


def test_paths_exist_absolute_path_is_taken_as_is(project: Project) -> None:
    existing = project.write("top.md")
    result = run("paths_exist", file_prompt(project, "docs/a.md", f"see {existing}"))
    assert result.status == "passed"
    assert result.detected == (str(existing),)


def test_paths_exist_tilde_resolves_through_the_home_directory(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(project.root))
    monkeypatch.setenv("USERPROFILE", str(project.root))
    project.write("notes.md")
    result = run("paths_exist", file_prompt(project, "docs/a.md", "see ~/notes.md"))
    assert result.status == "passed"
    assert result.detected == ("~/notes.md",)


# file-only lints on a text prompt, and formats


@pytest.mark.parametrize("name", ["markdown_links", "paths_exist"])
def test_file_only_lint_is_skipped_on_a_text_prompt(name: str) -> None:
    result = run(name, Prompt("see [x](./missing.md)"))
    assert result.status == "skipped"
    assert result.findings == ()


@pytest.mark.parametrize("name", ["anthropic-skill", "anthropic-claude"])
def test_format_runs_nothing_and_passes(name: str) -> None:
    result = run(name, Prompt("anything at all"))
    assert result.status == "passed"
    assert result.findings == ()
