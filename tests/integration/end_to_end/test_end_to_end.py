"""A realistic project run end to end: the project under `fixture/` exercises every
static feature of specs/static-checking.md and specs/templates.md, and a full run passes."""

import re
from pathlib import Path

import pytest
from conftest import Project

from skilleval import ExitCode

FIXTURE = Path(__file__).parent / "fixture"
FILE = "evals/skills.eval.yml"
SKILL = ".claude/skills/refactor/SKILL.md"

# File order, dependencies first, fan-out sorted, `fixtures/` excluded, the inline prompt nameless.
NODE_IDS = [
    f"{FILE}::house-style[{SKILL}]",
    f"{FILE}::house-style[.claude/skills/review/SKILL.md]",
    f"{FILE}::root-instructions[CLAUDE.md]",
    f"{FILE}::inline",
]


def test_collect_only_lists_every_case_in_order(project: Project) -> None:
    project.copy(FIXTURE)
    code, out = project.cli("--collect-only", "evals")
    assert code == ExitCode.OK
    assert [line for line in out.splitlines() if "::" in line] == NODE_IDS


def test_a_project_satisfying_every_check_passes(project: Project) -> None:
    project.copy(FIXTURE)
    code, out = project.cli("evals")
    assert code == ExitCode.OK
    assert "4 passed" in out
    assert "2 warnings" in out  # the `words` budget, at warn, once per SKILL.md
    assert "FAILED" not in out
    assert "ERROR" not in out


@pytest.mark.parametrize("old, new, check", [
    ("## Stopping", "## Stopping\n\nTODO: tidy this section.", "matches_none"),
    ("./reference.md", "./missing.md", "paths_exist"),
], ids=["template-constraint", "lint-inherited-at-warn-bare-in-the-test"])
def test_one_violation_fails_the_run_and_names_the_check(project: Project, old: str, new: str, check: str) -> None:
    project.copy(FIXTURE)
    path = project.root / SKILL
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8")
    code, out = project.cli("evals")
    assert code == ExitCode.TESTS_FAILED
    assert f"{NODE_IDS[0]} FAILED" in out.splitlines()
    assert re.search(rf"^\s+{check}: ", out, re.MULTILINE)
    assert "1 failed" in out
    assert "2 passed" in out
    assert "1 skipped" in out  # root-instructions needs house-style
