"""`skilleval.evaluation.harness.claude_code`, through `harness.ask`, with a program of our own
named `claude` on the `PATH`: what Claude Code is run with, and the reply read from what it
prints."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import tree

from skilleval.evaluation.harness import HarnessError, Reply, ask
from skilleval.testfile import Setup, TextPrompt

PROGRAM = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
here = Path(__file__).parent
(here / "run.json").write_text(json.dumps({{"args": sys.argv[1:], "input": sys.stdin.read(), "cwd": os.getcwd()}}))
sys.stdout.write((here / "prints").read_text())
sys.stderr.write("claude: not logged in")
sys.exit(int((here / "code").read_text()))
"""
USED = {"inputTokens": 1, "outputTokens": 20, "cacheReadInputTokens": 300, "cacheCreationInputTokens": 4000, "costUSD": 9}
RESULT = {
    "result": "Done.", "session_id": "session-1", "total_cost_usd": 0.25, "is_error": False, "subtype": "success",
    "modelUsage": {"claude-sonnet-5": USED, "claude-haiku-4-5": USED}, "permission_denials": [],
}
ASKED = ["--print", "--output-format", "json", "--model", "claude-sonnet-5"]
ASKING = ["--permission-mode", "manual", "--permission-prompts", "none"]
BEFORE = Reply("Done.", "session-1", 100, 0.25)
SETUP = Setup("user_local")


@dataclass
class Claude:
    """The program: `prints` sets what its next run prints and the code it ends with, `run`
    is what its last run was given."""

    folder: Path

    def prints(self, printed: Any = RESULT, code: int = 0, **changed: Any) -> None:
        (self.folder / "prints").write_text(json.dumps(printed | changed) if isinstance(printed, dict) else printed)
        (self.folder / "code").write_text(str(code))

    @property
    def run(self) -> dict[str, Any]:
        run: dict[str, Any] = json.loads((self.folder / "run.json").read_text())
        return run


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Claude:
    folder = tmp_path / "bin"
    folder.mkdir()
    (folder / "claude").write_text(PROGRAM)
    (folder / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", str(folder))
    program = Claude(folder)
    program.prints()
    return program


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    folder = tmp_path / "workspace"
    folder.mkdir()
    return folder


def skill(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\nHow to {name}.\n")
    return folder


@pytest.mark.parametrize("setup, previous, budget, args", [
    (Setup("user_local"), None, None, [*ASKED, *ASKING]),
    (Setup("user_local", "bypass"), None, None, [*ASKED, "--permission-mode", "bypassPermissions"]),
    (Setup("user_local", override_system_prompt=TextPrompt("Be brief.")), None, None, [*ASKED, *ASKING, "--system-prompt", "Be brief."]),
    (Setup("user_local", append_system_prompt=TextPrompt("")), None, None, [*ASKED, *ASKING, "--append-system-prompt", ""]),
    (Setup("user_local"), None, 1.5, [*ASKED, *ASKING, "--max-budget-usd", "1.5"]),
    (Setup("user_local"), BEFORE, 1.5, [*ASKED, *ASKING, "--max-budget-usd", "1.25", "--resume", "session-1"]),
], ids=["asking by default", "bypassing", "its system prompt replaced", "or added to, by nothing here", "a budget",
        "the conversation resumed, with what is left of the budget"])
def test_claude_code_is_run_in_the_workspace_with_the_setup_and_the_task_as_its_input(
    claude: Claude, workspace: Path, setup: Setup, previous: Reply | None, budget: float | None, args: list[str]
) -> None:
    ask("--help me: what is a qubit?", setup, "claude-sonnet-5", workspace, previous, max_tokens=10, max_budget_usd=budget)
    assert claude.run == {"args": args, "input": "--help me: what is a qubit?", "cwd": str(workspace)}


@pytest.mark.parametrize("changed, expected", [
    ({}, Reply("Done.", "session-1", 8642, 0.25)),
    ({"permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "rm -rf /", "description": "Tidy"}},
                             {"tool_name": "Edit", "tool_input": {"file_path": "utils.py"}}]},
     Reply("Done.", "session-1", 8642, 0.25, "Bash(rm -rf /)")),
    ({"is_error": True, "subtype": "error_max_budget_usd", "result": None}, Reply("", "session-1", 8642, 0.25)),
], ids=["every kind of token of every model counts", "the first action refused", "stopped at the budget"])
def test_the_reply_is_read_from_the_result_claude_code_prints(
    claude: Claude, workspace: Path, changed: dict[str, Any], expected: Reply
) -> None:
    claude.prints(**changed)
    assert ask("Say hi.", SETUP, "claude-sonnet-5", workspace) == expected


@pytest.mark.parametrize("printed, code, reason", [
    (RESULT | {"is_error": True, "result": "There's an issue with the selected model"}, 1, "issue with the selected model"),
    (RESULT | {"is_error": True, "subtype": "error_during_execution", "result": None, "errors": ["it broke"]}, 1, "it broke"),
    ("", 1, "claude: not logged in"),
    ("Done.", 0, "Done."),
    ("[]", 0, "[]"),
    ("{}", 0, "{}"),
], ids=["a model it does not know", "a run that broke", "nothing printed", "no JSON", "no result", "an empty result"])
def test_a_run_that_fails_or_prints_no_result_is_a_harness_error_saying_why(
    claude: Claude, workspace: Path, printed: Any, code: int, reason: str
) -> None:
    claude.prints(printed, code)
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", SETUP, "claude-sonnet-5", workspace)
    assert reason in str(info.value)


def test_a_skill_that_cannot_be_copied_is_a_harness_error(claude: Claude, workspace: Path, tmp_path: Path) -> None:
    setup = Setup("user_local", skills=(skill(tmp_path / "refactor", "refactor"),))
    (workspace / ".claude/skills").mkdir(parents=True)
    (workspace / ".claude/skills/refactor").write_text("a file where the skill goes")
    with pytest.raises(HarnessError):
        ask("Say hi.", setup, "claude-sonnet-5", workspace)


def test_skills_are_copied_into_the_workspace_under_their_names_when_the_conversation_starts(
    claude: Claude, workspace: Path, tmp_path: Path
) -> None:
    setup = Setup("user_local", skills=(skill(tmp_path / "skills/tidy", "refactor"), skill(tmp_path / "deploy", "deploy")))
    skill(workspace / ".claude/skills/review", "review")
    before = tree(workspace)
    added = {f".claude/skills/{name}/SKILL.md": f"---\nname: {name}\n---\nHow to {name}.\n" for name in ("refactor", "deploy")}
    ask("Say hi.", setup, "claude-sonnet-5", workspace, BEFORE)
    assert tree(workspace) == before
    ask("Say hi.", setup, "claude-sonnet-5", workspace)
    assert tree(workspace) == before | added


@pytest.mark.parametrize("where", ["the workspace", "the configuration of the user"])
def test_a_skill_named_as_one_of_claude_codes_own_is_a_harness_error_naming_both_and_runs_nothing(
    claude: Claude, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "configuration"))
    holder = workspace / ".claude" if where == "the workspace" else tmp_path / "configuration"
    own = skill(holder / "skills/tidy", "refactor")
    added = skill(tmp_path / "refactor", "refactor")
    setup = Setup("user_local", skills=(added,))
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", workspace)
    assert all(str(folder) in str(info.value) for folder in (own, added))
    assert not (claude.folder / "run.json").exists()
