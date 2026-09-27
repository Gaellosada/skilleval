"""`skilleval.evaluation.harness.ask`, as far as it goes with no harness to run: `conftest`
empties `PATH`, so no test ever starts one."""

from pathlib import Path

import pytest
from conftest import todo

from skilleval.evaluation.harness import HarnessError, ask
from skilleval.testfile import FilePrompt, Setup

pytestmark = todo


def test_a_missing_harness_is_a_harness_error(tmp_path: Path) -> None:
    setup = Setup("user_local")
    with pytest.raises(HarnessError):
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)


def test_a_system_prompt_file_that_cannot_be_read_is_a_harness_error_naming_it(tmp_path: Path) -> None:
    setup = Setup("user_local", override_system_prompt=FilePrompt(tmp_path / "missing.md"))
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)
    assert str(tmp_path / "missing.md") in str(info.value)


def test_two_skills_of_one_name_are_a_harness_error_naming_both_directories(tmp_path: Path) -> None:
    skills = (tmp_path / "mine/refactor", tmp_path / "theirs/refactor")
    for skill in skills:
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: refactor\ndescription: Refactors.\n---\n")
    setup = Setup("user_local", skills=skills)
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", tmp_path)
    assert all(str(skill) in str(info.value) for skill in skills)
