"""The worked examples in specs/examples run end to end against a project built to satisfy them."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from conftest import Project

EXAMPLES = Path(__file__).parent.parent / "specs" / "examples"
STATIC = "static-test.eval.yml"
TEMPLATES = "shared-templates.eval.yml"
SKILL = ".claude/skills/refactor/SKILL.md"

# Satisfies every check of `skills` and of both templates: 50-400 words, under 120 lines,
# `Usage` and `Examples` 1-3 times each, `test`/`tests`/`pytest` at least twice in total,
# a `## ` heading, `pytest -q`, no TODO/FIXME, one bash block, a posix path that exists, a
# URL on an allowed host, no banned word, no invisible character, no markdown link.
SKILL_TEXT = """\
---
name: refactor
description: Restructure Python code in small steps that keep the suite green.
---

# Refactor

## Usage

Apply this skill when the user asks to restructure existing Python code without
changing what it does. Read the module first, then make one change at a time and
run the tests after each step, so every step stays small enough to revert alone.
The catalogue of refactorings lives in ./reference.md next to this file, and the
conventions for skill files are described at https://docs.anthropic.com/skills.

## Examples

Extract a function from a long method, rename a variable across a module, or
replace a chain of conditionals with a lookup table. After each change, run the
whole test suite from the project root:

```bash
pytest -q
```

## Stopping

Stop as soon as pytest reports a failure and say which refactoring broke it.
"""

FIXTURE_TEXT = """\
---
name: fixture
description: Test data for the refactor skill.
---

# Fixture

A minimal skill file used as test data.
"""

CLAUDE_TEXT = """\
# Project

Run `pytest -q` before every commit and keep functions short.
"""

EXPECTED_IDS = [
    f"{STATIC}::shared-rules[{SKILL}]",
    f"{STATIC}::shared-rules[.claude/skills/refactor/fixtures/SKILL.md]",
    f"{STATIC}::skills[{SKILL}]",
    f"{STATIC}::root-instructions[CLAUDE.md]",
]


def build(project: Project) -> None:
    """Copy both example files in (names kept) and create everything they refer to."""
    for name in (STATIC, TEMPLATES):
        shutil.copy(EXAMPLES / name, project.root / name)
    project.write("banned-words.txt", "Simply\nObviously\n")
    project.write(SKILL, SKILL_TEXT)
    project.write(".claude/skills/refactor/reference.md", "# Refactorings\n\nExtract function.\n")
    project.write(".claude/skills/refactor/fixtures/SKILL.md", FIXTURE_TEXT)
    project.write("CLAUDE.md", CLAUDE_TEXT)


def test_collect_only_lists_the_expected_node_ids(project: Project) -> None:
    build(project)
    code, out = project.cli("--collect-only", STATIC, TEMPLATES)
    assert code == 0
    assert [line for line in out.splitlines() if "::" in line] == EXPECTED_IDS


def test_a_project_satisfying_every_check_passes(project: Project) -> None:
    build(project)
    code, out = project.cli(STATIC, TEMPLATES)
    assert code == 0
    assert "4 passed" in out
    assert "FAILED" not in out


def test_one_violation_fails_the_run_and_names_the_check(project: Project) -> None:
    build(project)
    project.write(SKILL, SKILL_TEXT + "\nTODO: tidy this section.\n")
    code, out = project.cli(STATIC, TEMPLATES)
    assert code == 1
    assert f"{EXPECTED_IDS[2]} FAILED" in out.splitlines()
    assert re.search(r"^\s+matches_none: ", out, re.M)
    assert "1 failed" in out
    assert "3 passed" in out
