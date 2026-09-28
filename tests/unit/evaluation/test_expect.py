"""`skilleval.evaluation.expect.check`: the reply and the files of the workspace, checked as a
prompt is."""

from dataclasses import replace
from pathlib import Path

import pytest

from skilleval.evaluation.expect import check
from skilleval.static import run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check, Expectation

WORDS = Check("words", {"min": None, "max": 3})
FOUR_WORDS = "see utils/strings.py for details"


def test_reply_checks_run_as_on_a_prompt_and_never_read_the_workspace(tmp_path: Path) -> None:
    mentions = Check("contains", {"words": ["utils/strings.py"], "occurrences": {"min": 1, "max": None}, "case_sensitive": False})
    checks = (WORDS, replace(WORDS, severity="warn"), mentions)
    checked = check((Expectation(None, checks),), FOUR_WORDS, tmp_path)
    assert checked == tuple(replace(run_check(c, Prompt(FOUR_WORDS)), prefix="response") for c in checks)
    assert [result.status for result in checked] == ["failed", "warned", "passed"]


@pytest.mark.parametrize("content, checks, severity, expected", [
    (FOUR_WORDS.encode(), (WORDS,), None, [("file", "passed"), ("words", "failed")]),
    (FOUR_WORDS.encode(), (), None, [("file", "passed")]),
    (None, (WORDS,), None, [("file", "failed")]),
    (None, (WORDS,), "warn", [("file", "warned")]),
    (b"\xff\xfe", (WORDS,), None, [("file", "failed")]),
], ids=["checked", "only has to exist", "missing", "missing, as a warning", "not UTF-8 text"])
def test_a_file_is_read_from_the_workspace_and_checked_only_when_it_is_there_as_text(
    tmp_path: Path, content: bytes | None, checks: tuple[Check, ...], severity: str | None, expected: list[tuple[str, str]]
) -> None:
    if content is not None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/notes.md").write_bytes(content)
    checked = check((Expectation("docs/notes.md", checks, severity),), "the reply", tmp_path)
    assert [(result.prefix, result.check.name, result.status) for result in checked] == [
        ("docs/notes.md", name, status) for name, status in expected
    ]
    assert all(result.findings for result in checked if result.status != "passed")


def test_a_path_that_cannot_be_one_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    (checked,) = check((Expectation("a\0b", (WORDS,)),), "the reply", tmp_path)
    assert (checked.check.name, checked.status) == ("file", "failed")
