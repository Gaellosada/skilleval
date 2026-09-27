"""`skilleval.evaluation.harness.ask`, as far as it goes with no harness to run: `PATH` is
emptied, so no test here ever starts one."""

from pathlib import Path

import pytest
from conftest import todo

from skilleval.evaluation.harness import HarnessError, ask
from skilleval.testfile import Setup

pytestmark = todo


@pytest.fixture(autouse=True)
def no_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))


def test_a_missing_harness_is_a_harness_error(tmp_path: Path) -> None:
    with pytest.raises(HarnessError):
        ask("Say hi.", Setup("user_local"), "claude-sonnet-5", tmp_path)


def test_two_skills_of_one_name_are_a_harness_error_naming_the_skill_and_both_directories(tmp_path: Path) -> None:
    skills = (tmp_path / "mine/refactor", tmp_path / "theirs/refactor")
    for skill in skills:
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: refactor\ndescription: Refactors.\n---\n")
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", Setup("user_local", skills=skills), "claude-sonnet-5", tmp_path)
    assert all(str(named) in str(info.value) for named in ("refactor", *skills))
