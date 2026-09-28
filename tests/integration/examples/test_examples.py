"""The worked examples of specs/examples, collected in a project holding the files they name."""

import shutil
from pathlib import Path

from conftest import Project

from skilleval import ExitCode

EXAMPLES = Path(__file__).parents[3] / "specs/examples"
SKILL = ".claude/skills/refactor/SKILL.md"
NAMED = [
    "CLAUDE.md", SKILL, "evals/banned-words.txt", "evals/prompts/reviewer.md",
    "evals/fixtures/pr-42/pr.diff", "evals/fixtures/pr-43/pr.diff", "evals/fixtures/utils/utils/strings.py",
    "evals/fixtures/skills/fake-deploy/SKILL.md",
]
IDS = [
    "reviewer-prompt[evals/prompts/reviewer.md]", "review", "review-on-sonnet", "implement", "review-inline",
    "review-appended", "review-bare", f"shared-rules[{SKILL}]", f"skills[{SKILL}]", "root-instructions[CLAUDE.md]",
]


def test_every_worked_example_loads(project: Project) -> None:
    for path in NAMED:
        project.write(path, "TODO\n")
    shutil.copytree(EXAMPLES, project.root / "evals", dirs_exist_ok=True)
    code, out = project.cli("--collect-only", "evals")
    assert code == ExitCode.OK
    assert [line.split("::")[1] for line in out.splitlines()] == IDS
