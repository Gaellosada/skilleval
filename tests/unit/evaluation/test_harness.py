"""`skilleval.evaluation.harness.ask`, as far as it goes with no harness to run: `conftest`
empties `PATH`, so no test ever starts one."""

from pathlib import Path

import pytest

from skilleval.evaluation.harness import HarnessError, ask
from skilleval.evaluation.harness.base import skill_name
from skilleval.testfile import FilePrompt, Setup


def test_a_missing_harness_is_a_harness_error(tmp_path: Path) -> None:
    setup = Setup("user_local")
    with pytest.raises(HarnessError):
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)


def test_a_system_prompt_file_that_cannot_be_read_is_a_harness_error_naming_it(tmp_path: Path) -> None:
    setup = Setup("user_local", override_system_prompt=FilePrompt(tmp_path / "missing.md"))
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)
    assert str(tmp_path / "missing.md") in str(info.value)


def test_two_skills_of_one_name_in_their_frontmatter_are_a_harness_error_naming_both_directories(tmp_path: Path) -> None:
    skills = (tmp_path / "mine/refactor", tmp_path / "theirs/tidy")
    for skill in skills:
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: refactor\ndescription: Refactors.\n---\n")
    setup = Setup("user_local", skills=skills)
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)
    assert all(str(skill) in str(info.value) for skill in skills)


@pytest.mark.parametrize("text, name", [
    ("---\ndescription: Refactors.\nname: tidy\n---\n", "tidy"),
    ("---\r\nname: tidy\r\n---\r\n", "tidy"),
    ("---\ndescription: Refactors.\n---\nname: tidy\n", "refactor"),
    ("---\nname: tidy\n", "refactor"),
    ("name: tidy\n", "refactor"),
    ("", "refactor"),
], ids=["in the frontmatter", "with Windows line ends", "none in the frontmatter", "a frontmatter never closed",
        "no frontmatter", "an empty file"])
def test_a_skill_is_named_by_its_frontmatter_and_without_a_name_there_by_its_directory(
    tmp_path: Path, text: str, name: str
) -> None:
    (tmp_path / "refactor").mkdir()
    (tmp_path / "refactor/SKILL.md").write_bytes(text.encode())
    assert skill_name(tmp_path / "refactor") == name


@pytest.mark.parametrize("content", [None, b"\xff\xfe", b"---\nname: [tidy\n---\n"],
                         ids=["missing", "not UTF-8 text", "a frontmatter that is not YAML"])
def test_a_skill_file_that_cannot_be_read_is_a_harness_error_naming_the_skill(tmp_path: Path, content: bytes | None) -> None:
    if content is not None:
        (tmp_path / "SKILL.md").write_bytes(content)
    with pytest.raises(HarnessError) as info:
        skill_name(tmp_path)
    assert str(tmp_path) in str(info.value)
