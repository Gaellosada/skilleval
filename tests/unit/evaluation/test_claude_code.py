"""`skilleval.evaluation.harness.claude_code`, through `harness.ask`, with a program of our own
named `claude` on the `PATH`: what Claude Code is run with, and the reply read from the JSON
lines it prints, the result last."""

import json
import os
import stat
import sys
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import pytest
from conftest import tree

from skilleval.evaluation import harness
from skilleval.evaluation.config import Config
from skilleval.evaluation.harness import HarnessError, Reply, claude_code
from skilleval.testfile import FilePrompt, Setup, TextPrompt

CLAUDES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDECODE")  # Claude Code reads them
ENVIRONMENT = ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", *CLAUDES, "INHERITED")  # what the program records of it
PROGRAM = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
here = Path(__file__).parent
given = sys.stdin.buffer.read().decode("utf-8")
(here / "run.json").write_text(json.dumps({{"args": sys.argv[1:], "input": given, "cwd": os.getcwd()}}))
(here / "env.json").write_text(json.dumps({{name: os.environ.get(name) for name in {ENVIRONMENT!r}}}))
configuration = os.environ.get("CLAUDE_CONFIG_DIR")
(here / "found.json").write_text(json.dumps(sorted(os.listdir(configuration)) if configuration and os.path.isdir(configuration) else None))
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
ask = partial(harness.ask, config=Config(Path(".skilleval/config.yml")))  # the default settings: backend claude_cli
KEY, TOKEN = "sk-ant-api03-key", "sk-ant-oat01-token"
LOGGED_IN = Config(Path(".skilleval/config.yml"), claude_code_oauth_token=TOKEN)  # what blank logs in with


@dataclass
class Claude:
    """The program: `prints` sets what its next run prints and the code it ends with, a result
    as the last of the JSON lines of `STREAM`, `run` is what its last run was given, `env` the
    variables of `ENVIRONMENT` it had, `found` the files it found in `CLAUDE_CONFIG_DIR`."""

    folder: Path

    def prints(self, printed: Any = RESULT, code: int = 0, **changed: Any) -> None:
        if isinstance(printed, dict):
            printed = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in (*STREAM, printed | changed))
        (self.folder / "prints").write_bytes(printed.encode() if isinstance(printed, str) else printed)
        (self.folder / "code").write_text(str(code))

    @property
    def run(self) -> dict[str, Any]:
        run: dict[str, Any] = json.loads((self.folder / "run.json").read_text())
        return run

    @property
    def env(self) -> dict[str, Any]:
        env: dict[str, Any] = json.loads((self.folder / "env.json").read_text())
        return env

    @property
    def found(self) -> list[str] | None:
        found: list[str] | None = json.loads((self.folder / "found.json").read_text())
        return found


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


@pytest.mark.parametrize("task, read", [
    ("Say hi, précisément.\nThen stop.", "Say hi, précisément.\nThen stop."),
    ("Fix \ud800 this.", "Fix ? this."),
], ids=["text that is not ASCII, kept readable", "a lone surrogate, as YAML reads \\uD800"])
def test_the_transcript_is_the_task_as_the_model_read_it_then_every_line_claude_code_printed(
    claude: Claude, workspace: Path, task: str, read: str
) -> None:
    first, printed = ask(task, SETUP, "claude-sonnet-5", workspace).transcript.split("\n", 1)
    assert claude.run["input"] == read
    assert first == json.dumps({"type": "user", "message": {"role": "user", "content": read}}, ensure_ascii=False)
    assert printed == (claude.folder / "prints").read_text(encoding="utf-8")


def test_the_transcript_ends_the_last_line_claude_code_left_open(claude: Claude, workspace: Path) -> None:
    claude.prints(json.dumps(RESULT))
    assert ask("Say hi.", SETUP, "claude-sonnet-5", workspace).transcript.endswith(json.dumps(RESULT) + "\n")


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
    (b"\xff\xfe{", 0, "no result to read"),
], ids=["a model it does not know", "a run that broke", "or stopped, saying only how", "nothing printed", "no JSON",
        "no result", "an empty result", "a result of another shape", "a cost that is no number",
        "errors that are no text", "a stream cut before its result", "output that is not UTF-8"])
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


@pytest.mark.parametrize("name", ["user_local", "blank"])
def test_a_skill_is_copied_without_anything_named_skilleval_at_any_depth(
    claude: Claude, workspace: Path, tmp_path: Path, name: str
) -> None:
    tested = skill(tmp_path / "refactor", "refactor")  # a skill tested by a file beside its SKILL.md, with no root
    skillevals = {".skilleval/config.yml": "CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-token\n",
                  ".skilleval/results/refactor.eval.yml/t/conversation.jsonl": "{}\n", "reference/.skilleval/config.yml": ""}
    for path, text in {"reference/api.md": "The API.", **skillevals}.items():
        (tested / path).parent.mkdir(parents=True, exist_ok=True)
        (tested / path).write_text(text)
    before = tree(tested)
    harness.ask("Say hi.", Setup(name, skills=(tested,)), "claude-sonnet-5", workspace, config=LOGGED_IN)
    assert tree(workspace) == {f".claude/skills/refactor/{path}": text for path, text in before.items() if path not in skillevals}
    assert list(workspace.rglob(".skilleval")) == []
    assert tree(tested) == before


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


# blank


@pytest.mark.parametrize("name, changed", [
    ("user_local", {}),
    ("blank", {"CLAUDE_CONFIG_DIR": ANY, "CLAUDE_CODE_OAUTH_TOKEN": TOKEN} | dict.fromkeys(CLAUDES)),
], ids=["user_local, as it is", "blank, logged in with the token of the settings and nothing else of claude code's"])
def test_both_harnesses_run_the_same_command_in_the_environment_of_skilleval_blank_taking_out_what_claude_code_reads(
    claude: Claude, workspace: Path, monkeypatch: pytest.MonkeyPatch, name: str, changed: dict[str, Any]
) -> None:
    for variable in (*CLAUDES, "INHERITED"):
        monkeypatch.setenv(variable, KEY if variable == "ANTHROPIC_API_KEY" else "1")
    inherited = {variable: os.environ.get(variable) for variable in ENVIRONMENT}
    harness.ask("Say hi.", Setup(name), "claude-sonnet-5", workspace, config=LOGGED_IN)
    assert claude.run == {"args": [*ASKED, *ASKING], "input": "Say hi.", "cwd": str(workspace)}
    assert claude.env == inherited | changed


def test_blank_has_a_configuration_directory_of_its_workspace_emptied_by_the_first_task_and_kept_for_the_next(
    claude: Claude, tmp_path: Path
) -> None:
    def configuration(workspace: Path, previous: Reply | None = None) -> tuple[Path, list[str] | None]:
        """The configuration directory of the run in `workspace`, with what the run found in it."""
        harness.ask("Say hi.", Setup("blank"), "claude-sonnet-5", workspace, previous, config=LOGGED_IN)
        return Path(claude.env["CLAUDE_CONFIG_DIR"]), claude.found

    workspace, other = tmp_path / "split-utils", tmp_path / "other"
    for folder in (workspace, other):
        folder.mkdir()
    folder, found = configuration(workspace)
    assert (folder.parent, found) == (Path(tempfile.gettempdir(), claude_code.BLANK), [])
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700  # the user's alone to read
    assert "skilleval" not in str(folder).lower()
    assert workspace.name not in str(folder)
    assert not folder.is_relative_to(workspace)
    assert not workspace.is_relative_to(folder)
    (folder / "session.jsonl").write_text("left by the task")
    assert configuration(workspace, BEFORE) == (folder, ["session.jsonl"])
    assert configuration(workspace) == (folder, [])
    assert configuration(other)[0] != folder


def test_blank_without_a_token_is_a_harness_error_naming_the_settings_file_and_runs_nothing(
    claude: Claude, workspace: Path, tmp_path: Path
) -> None:
    config, setup = Config(tmp_path / ".skilleval/config.yml"), Setup("blank")
    with pytest.raises(HarnessError) as info:
        harness.ask("Say hi.", setup, "claude-sonnet-5", workspace, config=config)
    assert "CLAUDE_CODE_OAUTH_TOKEN" in str(info.value)
    assert str(config.path) in str(info.value)
    assert not (claude.folder / "run.json").exists()


def test_a_blank_configuration_directory_that_cannot_be_made_is_a_harness_error_and_runs_nothing(
    claude: Claude, workspace: Path
) -> None:
    Path(tempfile.gettempdir(), claude_code.BLANK).write_text("a file where the configuration directories go")
    setup = Setup("blank")
    with pytest.raises(HarnessError):
        harness.ask("Say hi.", setup, "claude-sonnet-5", workspace, config=LOGGED_IN)
    assert not (claude.folder / "run.json").exists()


@pytest.mark.parametrize("where, clash", [("configuration", False), ("workspace/.claude", True)],
                         ids=["the user's configuration, not there", "the workspace, still there"])
def test_blank_takes_the_names_of_the_skills_of_the_workspace_alone(
    claude: Claude, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, clash: bool
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "configuration"))
    skill(tmp_path / where / "skills/refactor", "tidy")
    setup = Setup("blank", skills=(skill(tmp_path / "mine", "refactor"),))
    with pytest.raises(HarnessError, match="two skills are named refactor") if clash else nullcontext():
        harness.ask("Say hi.", setup, "claude-sonnet-5", workspace, config=LOGGED_IN)
    assert (claude.folder / "run.json").exists() is not clash


@pytest.mark.parametrize("name, changed, refused", [
    ("blank", {"api_error_status": 401}, True),
    ("user_local", {"api_error_status": 401}, False),
    ("blank", {}, False),
    ("blank", {"api_error_status": 500}, False),
], ids=["blank, its token refused", "user_local, logged in as its user", "blank, another failure", "blank, an error of the API"])
def test_a_token_claude_code_refuses_under_blank_is_a_harness_error_naming_the_settings_file_after_what_claude_code_said(
    claude: Claude, workspace: Path, name: str, changed: dict[str, Any], refused: bool
) -> None:
    claude.prints(code=1, is_error=True, result="Failed to authenticate.", **changed)
    setup = Setup(name)
    with pytest.raises(HarnessError) as info:
        harness.ask("Say hi.", setup, "claude-sonnet-5", workspace, config=LOGGED_IN)
    message = str(info.value)
    assert "Failed to authenticate." in message
    assert TOKEN not in message
    after = message.partition("Failed to authenticate.")[2]
    assert ("CLAUDE_CODE_OAUTH_TOKEN" in after, str(LOGGED_IN.path) in after) == (refused, refused)
