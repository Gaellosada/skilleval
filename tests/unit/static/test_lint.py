"""`run_check` on every lint check, per specs/static-checking.md."""

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import Project

from skilleval.static import CHECKS, CheckResult, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check
from skilleval.testfile.checks import FAMILY

INVISIBLE = ["\ufeff", "\u00a0", "\u202f", "\u200b", "\u200c", "\u200d", "\u2060"]


def test_every_check_name_the_loader_accepts_has_a_function():
    # passes against the skeleton by design: it pins values that already exist
    assert set(CHECKS) == set(FAMILY)


def run(name: str, prompt: Prompt, severity: str = "error") -> CheckResult:
    check = Check(name, {}, severity)
    result = run_check(check, prompt)
    assert result.check == check
    return result


def file_prompt(project: Project, rel: str, text: str, root: Path | None = None) -> Prompt:
    return Prompt(text, project.write(rel, text), root)


def assert_findings(result: CheckResult, found: Sequence[tuple[int, str]]) -> None:
    """One finding per `(line, word)`, in order: at that line, its message holding that word."""
    assert result.status == ("failed" if found else "passed")
    assert [f.line for f in result.findings] == [line for line, _ in found]
    for finding, (_, word) in zip(result.findings, found, strict=True):
        assert word in finding.message


# chars: exactly seven codepoints, one finding per occurrence with its line and escaped codepoint


@pytest.mark.parametrize(("text", "found"), [
    *[(f"clean\nbad{c}here", [(2, c)]) for c in INVISIBLE],
    ("\ufeffhello", [(1, "\ufeff")]),
    ("a\u00a0b\u00a0c\nd\n\u200be", [(1, "\u00a0"), (1, "\u00a0"), (3, "\u200b")]),  # one finding per occurrence
    *[(text, []) for text in ["", "“smart” and ‘quotes’", "windows\r\nline endings\r\n", "\ta tab\tinside",
                              "emoji \U0001f389 here", "accents café naïve"]],
], ids=[*(f"U+{ord(c):04X}" for c in INVISIBLE), "a BOM on line 1", "one finding per occurrence",
        "empty", "smart quotes", "CRLF", "tabs", "emoji", "accents"])
def test_chars_reports_each_of_seven_invisible_codepoints_with_its_line_and_nothing_else(
    text: str, found: list[tuple[int, str]]
) -> None:
    assert_findings(run("chars", Prompt(text)), [(line, f"U+{ord(char):04X}") for line, char in found])


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
    ("[x](mailto:a@b.c) [y](ftp://h/missing.md)", False, ()),  # any scheme is left alone, not only http(s)
    ("[x](C:/missing.md)", False, ((1, "C:/missing.md"),)),  # a drive letter is a path, not a scheme
    ('[x](missing.md "Title")', False, ((1, "missing.md"),)),  # a title does not hide a broken target
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
    assert_findings(run("markdown_links", file_prompt(project, "docs/a.md", text, project.root if with_root else None)), findings)


def test_markdown_links_anchor_into_a_target_that_cannot_be_read_matches_no_heading(project: Project) -> None:
    (project.root / "docs").mkdir()
    (project.root / "docs/b.md").write_bytes(b"# Usage \xff\n")
    result = run("markdown_links", file_prompt(project, "docs/a.md", "[x](b.md) [y](b.md#usage)"))
    assert [f.message for f in result.findings] == ["#usage matches no heading in b.md"]


# paths_exist: the prompt is docs/a.md; docs/b.md and docs/sub/c.py exist, so does top.md


@pytest.mark.parametrize(("text", "findings", "detected"), [
    ("see ./b.md, `sub/c.py` and ../top.md", (), ("./b.md", "sub/c.py", "../top.md")),  # from the file's directory
    ("see ./b.md\nand ./missing.md", ((2, "./missing.md"),), ("./b.md", "./missing.md")),
    ("in the sub/ tree", (), ("sub/",)),  # a directory counts
    ("```\nedit path/to/file.py\n```", (), ()),  # fenced blocks are skipped
    ("see ~nobody_xyz/notes.md", ((1, "~nobody_xyz/notes.md"),), ("~nobody_xyz/notes.md",)),  # only ~/ expands; ~user/ is checked as written, never raises
    ("see ./x.md and ./y.md\nand ./z.md", ((1, "./x.md"), (1, "./y.md"), (2, "./z.md")), ("./x.md", "./y.md", "./z.md")),
])
def test_paths_exist_resolves_every_path_outside_fences(
    project: Project, text: str, findings: tuple[tuple[int, str], ...], detected: tuple[str, ...]
) -> None:
    for existing in ("docs/b.md", "docs/sub/c.py", "top.md"):
        project.write(existing)
    result = run("paths_exist", file_prompt(project, "docs/a.md", text))
    assert_findings(result, findings)
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


# file-only lints on a text prompt


@pytest.mark.parametrize("name", ["markdown_links", "paths_exist"])
def test_file_only_lint_is_skipped_on_a_text_prompt(name: str) -> None:
    result = run(name, Prompt("see [x](./missing.md)"))
    assert result.status == "skipped"
    assert result.findings == ()


def test_markdown_links_reads_an_anchored_target_once_per_case(project: Project, reads: Counter[str]) -> None:
    project.write("docs/api.md", "# Usage\n")
    prompt = file_prompt(project, "docs/a.md", "[a](api.md#usage) [b](api.md#usage) [c](api.md#nope)")
    result = run("markdown_links", prompt)
    assert [f.line for f in result.findings] == [1]
    assert reads["api.md"] == 1


def test_a_path_the_filesystem_rejects_is_a_finding_not_a_crash(project: Project) -> None:
    long = "./" + "a" * 300 + ".md"  # one component over the 255-byte limit: Path.exists raises OSError
    result = run("paths_exist", file_prompt(project, "docs/a.md", f"see {long}"))
    assert [f.line for f in result.findings] == [1]
    result = run("markdown_links", file_prompt(project, "docs/a.md", f"[x]({long})"))
    assert [f.line for f in result.findings] == [1]
