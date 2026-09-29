"""`skilleval.evaluation.harness.claude_code`, through `harness.ask`, with a program of our own
named `claude` on the `PATH`: what Claude Code is run with, and the reply read from the JSON
lines it prints, the result last."""

import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from conftest import tree

from skilleval.evaluation.harness import HarnessError, Reply, ask
from skilleval.testfile import FilePrompt, Setup, TextPrompt

PROGRAM = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
here = Path(__file__).parent
given = sys.stdin.buffer.read().decode("utf-8")
(here / "run.json").write_text(json.dumps({{"args": sys.argv[1:], "input": given, "cwd": os.getcwd()}}))
sys.stdout.buffer.write((here / "prints").read_bytes())
sys.stderr.write("claude: not logged in")
sys.exit(int((here / "code").read_text()))
"""
USED = {"inputTokens": 1, "outputTokens": 20, "cacheReadInputTokens": 300, "cacheCreationInputTokens": 4000, "costUSD": 9}
STREAM = [  # what Claude Code prints before its result
    {"type": "system", "subtype": "init", "session_id": "session-1"},
    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Terminé."}]}},
]
RESULT = {
    "type": "result", "result": "Done.", "session_id": "session-1", "total_cost_usd": 0.25, "is_error": False, "subtype": "success",
    "modelUsage": {"claude-sonnet-5": USED, "claude-haiku-4-5": USED}, "permission_denials": [],
}
ASKED = ["--print", "--output-format", "stream-json", "--verbose", "--model", "claude-sonnet-5"]
ASKING = ["--permission-mode", "manual", "--permission-prompts", "none"]
BEFORE = Reply("Done.", "session-1", 100, 0.25, "")
SETUP = Setup("user_local")


@dataclass
class Claude:
    """The program: `prints` sets what its next run prints and the code it ends with, a result
    as the last of the JSON lines of `STREAM`, `run` is what its last run was given."""

    folder: Path

    def prints(self, printed: Any = RESULT, code: int = 0, **changed: Any) -> None:
        if isinstance(printed, dict):
            printed = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in (*STREAM, printed | changed))
        (self.folder / "prints").write_text(printed, encoding="utf-8")
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
    (folder / "claude").chmod(0o700)
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
    ask("--help me: what is a qubit, précisément?", setup, "claude-sonnet-5", workspace, previous, max_tokens=10, max_budget_usd=budget)
    assert claude.run == {"args": args, "input": "--help me: what is a qubit, précisément?", "cwd": str(workspace)}


def test_a_system_prompt_file_is_given_as_its_text(claude: Claude, workspace: Path, tmp_path: Path) -> None:
    (tmp_path / "reviewer.md").write_text("Be brief.\n")
    ask("Say hi.", Setup("user_local", append_system_prompt=FilePrompt(tmp_path / "reviewer.md")), "claude-sonnet-5", workspace)
    assert claude.run["args"][-2:] == ["--append-system-prompt", "Be brief.\n"]


@pytest.mark.parametrize("changed, expected", [
    ({}, Reply("Done.", "session-1", 8642, 0.25, "")),
    ({"result": "Terminé."}, Reply("Terminé.", "session-1", 8642, 0.25, "")),
    ({"permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "rm -rf /", "description": "Tidy"}},
                             {"tool_name": "Edit", "tool_input": {"file_path": "utils.py"}}]},
     Reply("Done.", "session-1", 8642, 0.25, "", "Bash(rm -rf /)")),
    ({"permission_denials": [{"tool_name": "EnterPlanMode", "tool_input": {}}]},
     Reply("Done.", "session-1", 8642, 0.25, "", "EnterPlanMode()")),
    ({"is_error": True, "subtype": "error_max_budget_usd", "result": None}, Reply("", "session-1", 8642, 0.25, "")),
    ({"result": "a\u2028b\u2029c\u0085d"}, Reply("a\u2028b\u2029c\u0085d", "session-1", 8642, 0.25, "")),
], ids=["every kind of token of every model counts", "text that is not ASCII", "the first action refused",
        "an action that takes nothing", "stopped at the budget", "text holding what Python also reads as a line end"])
def test_the_reply_is_read_from_the_result_claude_code_prints_last(
    claude: Claude, workspace: Path, changed: dict[str, Any], expected: Reply
) -> None:
    claude.prints(**changed)
    assert replace(ask("Say hi.", SETUP, "claude-sonnet-5", workspace), transcript="") == expected


@pytest.mark.parametrize("task", ["Say hi, précisément.\nThen stop.", "Fix \ud800 this."],
                         ids=["text that is not ASCII", "a lone surrogate, as YAML reads \\uD800"])
def test_the_transcript_is_the_task_as_a_user_message_then_every_line_claude_code_printed(
    claude: Claude, workspace: Path, task: str
) -> None:
    transcript = ask(task, SETUP, "claude-sonnet-5", workspace).transcript
    transcript.encode("utf-8")  # conversation.jsonl is written as UTF-8
    first, printed = transcript.split("\n", 1)
    assert json.loads(first) == {"type": "user", "message": {"role": "user", "content": task}}
    assert printed == (claude.folder / "prints").read_text(encoding="utf-8")


@pytest.mark.parametrize("printed, code, reason", [
    (RESULT | {"is_error": True, "result": "There's an issue with the selected model"}, 1, "issue with the selected model"),
    (RESULT | {"is_error": True, "subtype": "error_during_execution", "result": None, "errors": ["it broke"]}, 1, "it broke"),
    (RESULT | {"is_error": True, "subtype": "error_max_turns", "result": None}, 1, "error_max_turns"),
    ("", 1, "claude: not logged in"),
    ("Done.", 0, "Done."),
    ("[]", 0, "[]"),
    ("{}", 0, "{}"),
    (RESULT | {"modelUsage": None}, 0, "modelUsage"),
    (RESULT | {"total_cost_usd": None}, 0, "total_cost_usd"),
    (RESULT | {"is_error": True, "result": None, "errors": [{"code": 529}]}, 1, "529"),
    ("".join(json.dumps(line) + "\n" for line in STREAM), 1, "claude: not logged in"),
], ids=["a model it does not know", "a run that broke", "or stopped, saying only how", "nothing printed", "no JSON",
        "no result", "an empty result", "a result of another shape", "a cost that is no number",
        "errors that are no text", "a stream cut before its result"])
def test_a_run_that_fails_or_prints_no_result_is_a_harness_error_saying_why(
    claude: Claude, workspace: Path, printed: Any, code: int, reason: str
) -> None:
    claude.prints(printed, code)
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", SETUP, "claude-sonnet-5", workspace)
    assert reason in str(info.value)


def test_a_run_stopped_at_the_budget_counts_more_than_it(claude: Claude, workspace: Path) -> None:
    assert ask("Say hi.", SETUP, "claude-sonnet-5", workspace, max_budget_usd=0.25).cost_usd == 0.25
    claude.prints(is_error=True, subtype="error_max_budget_usd", result=None)
    assert ask("Say hi.", SETUP, "claude-sonnet-5", workspace, max_budget_usd=0.25).cost_usd > 0.25
    assert ask("Say hi.", SETUP, "claude-sonnet-5", workspace, max_budget_usd=0.2).cost_usd == 0.25


def test_output_that_is_not_utf_8_is_a_harness_error(claude: Claude, workspace: Path) -> None:
    (claude.folder / "prints").write_bytes(b"\xff\xfe{")
    with pytest.raises(HarnessError, match="no result to read"):
        ask("Say hi.", SETUP, "claude-sonnet-5", workspace)


@pytest.mark.parametrize("program, model", [("not a program", "claude-sonnet-5"), (PROGRAM, "claude\0sonnet")],
                         ids=["no program", "a model no program can be given"])
def test_a_program_that_cannot_be_run_is_a_harness_error_naming_it(
    claude: Claude, workspace: Path, program: str, model: str
) -> None:
    (claude.folder / "claude").write_text(program)
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", SETUP, model, workspace)
    assert str(claude.folder / "claude") in str(info.value)


def test_a_skill_that_cannot_be_copied_is_a_harness_error_naming_it(claude: Claude, workspace: Path, tmp_path: Path) -> None:
    setup = Setup("user_local", skills=(skill(tmp_path / "refactor", "refactor"),))
    (workspace / ".claude/skills").mkdir(parents=True)
    (workspace / ".claude/skills/refactor").write_text("a file where the skill goes")
    with pytest.raises(HarnessError) as info:
        ask("Say hi.", setup, "claude-sonnet-5", workspace)
    assert str(tmp_path / "refactor") in str(info.value)


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


@pytest.mark.parametrize("where, configuration", [
    ("workspace/.claude", "elsewhere"), ("configuration", "configuration"), ("home/.claude", None), ("home/.claude", ""),
], ids=["the workspace", "the configuration of the user", "in their home by default", "or when it is named by nothing"])
def test_a_skill_named_as_the_directory_of_one_of_claude_codes_own_is_a_harness_error_naming_both_and_runs_nothing(
    claude: Claude, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, configuration: str | None
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    if configuration is not None:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", configuration and str(tmp_path / configuration))
    own = skill(tmp_path / where / "skills/refactor", "tidy")
    added = skill(tmp_path / "mine", "refactor")
    setup = Setup("user_local", skills=(added,))
    with pytest.raises(HarnessError, match="two skills are named refactor") as info:
        ask("Say hi.", setup, "claude-sonnet-5", workspace)
    assert all(str(folder) in str(info.value) for folder in (own, added))
    assert not (claude.folder / "run.json").exists()


def test_a_folder_of_the_users_skills_holding_no_skill_takes_no_name(
    claude: Claude, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "configuration"))
    (tmp_path / "configuration/skills/notes").mkdir(parents=True)
    (tmp_path / "configuration/skills/notes/today.md").write_text("Nothing.")
    ask("Say hi.", Setup("user_local", skills=(skill(tmp_path / "mine", "notes"),)), "claude-sonnet-5", workspace)
    assert (workspace / ".claude/skills/notes/SKILL.md").exists()
