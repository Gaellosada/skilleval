"""Claude Code, run headless: what the backend `claude_cli` runs. Each task is one run of
`claude --print` in the workspace, the task on its standard input, the next one resuming
the session of the one before. The harness `blank` is a run with a configuration of its
own, empty, in place of the user's. A judge is a run for an answer fitting a schema, with
none of what Claude Code would load for its user."""

import io
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from skilleval.evaluation.harness.base import HarnessError, Reply, Request, named, tail
from skilleval.evaluation.workspace import neutral
from skilleval.testfile.paths import HOME

PERMISSIONS = {
    # what would ask is refused, no one being there to answer
    "always_ask": ["--permission-mode", "manual", "--permission-prompts", "none"],
    "bypass": ["--permission-mode", "bypassPermissions"],
}
SKILLS = Path(".claude", "skills")  # where Claude Code looks for the skills of a project
BLANK = "c-4be71d"  # the folder of the blank configurations: the model can read the name, so it says nothing
OWN = ("ANTHROPIC_", "CLAUDE")  # what starts the name of a variable Claude Code reads: a login, a model, a setting
EFFORT = "CLAUDE_CODE_EFFORT_LEVEL"  # what Claude Code puts above --effort, and above the effort of a skill or subagent
TOKENS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
# a judge has no tool, no server, no settings file of the user, the project or the folder, and leaves no session
ALONE = ["--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence"]


def ask(request: Request) -> Reply:
    """Run Claude Code on the task of `request` and read its reply. The dollar limit stops it
    mid-task. Raises `HarnessError`."""
    setup, previous = request.setup, request.previous
    environment = _blank(request) if setup.harness == "blank" else dict(os.environ)
    environment.pop(EFFORT, None)  # the user's, which would replace the test's
    if previous is None:
        _add_skills(setup.skills, request.folder, environment)
    program = shutil.which("claude")
    if program is None:
        raise HarnessError("no claude program on the PATH: install Claude Code, which the backend claude_cli runs, "
                           f"or change backend in {request.config.path}")
    command = [program, "--print", "--output-format", "stream-json", "--verbose", "--model", request.model]
    command += ["--effort", setup.effort]
    command += PERMISSIONS[setup.permissions]
    if request.system_prompt is not None:
        flag = "--system-prompt" if setup.override_system_prompt else "--append-system-prompt"
        command += [flag, request.system_prompt]
    if request.max_budget_usd is not None:  # Claude Code counts what one run spends
        command += ["--max-budget-usd", str(request.max_budget_usd - (previous.cost_usd if previous else 0))]
    if previous is not None:
        command += ["--resume", previous.conversation]
    if request.schema is not None:
        command += ["--json-schema", json.dumps(request.schema), *ALONE]
    # ponytail: max_tokens is checked by the caller once the task ends, Claude Code having no
    # such limit; to stop mid-task, read the JSON lines as they come and count
    task = request.task.encode("utf-8", "replace").decode()  # as the model reads it: UTF-8 holds no lone surrogate
    try:
        done = subprocess.run(
            command, input=task, cwd=request.folder, env=environment, capture_output=True, encoding="utf-8",
            errors="replace",
        )
    except (OSError, ValueError) as e:
        raise HarnessError(f"cannot run {program}: {e}") from e
    return _reply(done, task, request)


def _blank(request: Request) -> dict[str, str]:
    """The environment of a run of the harness `blank`: that of skilleval without the
    variables Claude Code reads, a login it would use over the token among them, with the
    token of the settings and a configuration directory of the workspace's own, emptied
    before the first task and the user's alone to read. It is in the system's temporary
    directory and its name says nothing, as `workspace.locate` has it. Raises `HarnessError`
    for settings holding no token, and for a directory that cannot be emptied."""
    config = request.config
    if config.claude_code_oauth_token is None:
        raise HarnessError("no CLAUDE_CODE_OAUTH_TOKEN, and the harness blank cannot log in without one: "
                           f"run claude setup-token and write what it prints in {config.path}")
    configuration = Path(tempfile.gettempdir(), BLANK, neutral(str(request.folder)))
    if request.previous is None:
        try:
            if configuration.exists():
                shutil.rmtree(configuration)
            configuration.mkdir(mode=0o700, parents=True)
        except OSError as e:
            raise HarnessError(f"cannot empty the configuration {configuration} of the harness blank: {e}") from e
    inherited = {name: value for name, value in os.environ.items() if not name.startswith(OWN)}
    return inherited | {"CLAUDE_CONFIG_DIR": str(configuration), "CLAUDE_CODE_OAUTH_TOKEN": config.claude_code_oauth_token}


def _add_skills(skills: tuple[Path, ...], folder: Path, environment: dict[str, str]) -> None:
    """Copy `skills` into the workspace `folder`, each under its name, where Claude Code, run
    with `environment`, finds them beside its own: those of its configuration and those the
    workspace holds, which it names after their directories. Nothing named `HOME` is copied,
    as `workspace.fill` copies none. Raises `HarnessError` for a skill named as one of these,
    or that cannot be copied."""
    configuration = Path(environment.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    own = {
        file.parent.name: file.parent
        for holder in (configuration / "skills", folder / SKILLS)
        for file in holder.glob("*/SKILL.md")
    }
    for name, skill in named(skills, own).items():
        try:
            shutil.copytree(skill, folder / SKILLS / name, ignore=shutil.ignore_patterns(HOME))
        except OSError as e:
            raise HarnessError(f"cannot copy the skill {skill} into the workspace: {e}") from e


def _reply(done: subprocess.CompletedProcess[str], task: str, request: Request) -> Reply:
    """The reply in the `_result` a run for `request` printed, its transcript a user message
    holding `task` as the run was given it, then every line printed, the last one ended, its
    output tokens the `outputTokens` of every model, its output what the result holds for a
    schema. A run stopped at the dollar limit is a reply, which counts more than the limit;
    any other that failed is a `HarnessError`, which names the token a harness `blank` was
    refused with, or, with no result to read, holds what the run wrote to its standard error
    and the `tail` of what it printed."""
    max_budget_usd = request.max_budget_usd
    asked = {"type": "user", "message": {"role": "user", "content": task}}
    transcript = json.dumps(asked, ensure_ascii=False) + "\n" + done.stdout.removesuffix("\n") + "\n"
    try:
        result = _result(done.stdout)
        tokens = sum(int(used[kind]) for used in result["modelUsage"].values() for kind in TOKENS)
        written = sum(int(used["outputTokens"]) for used in result["modelUsage"].values())
        text, cost, denials = str(result.get("result") or ""), float(result["total_cost_usd"]), result["permission_denials"]
        stopped = result["subtype"] == "error_max_budget_usd"
        if stopped and max_budget_usd is not None:  # Claude Code stops at the limit, not past it
            cost = max(cost, math.nextafter(max_budget_usd, math.inf))
        if result["is_error"] and not stopped:
            refused = request.setup.harness == "blank" and result.get("api_error_status") == 401
            hint = (f"; the harness blank logs in with the CLAUDE_CODE_OAUTH_TOKEN of {request.config.path}, or else "
                    "of the environment: run claude setup-token for a new one") if refused else ""
            raise HarnessError(f"Claude Code failed: {text or result.get('errors') or result['subtype']}{hint}")
        denied = _action(denials[0]) if denials else None
        return Reply(text, str(result["session_id"]), tokens, written, cost, transcript, denied, result.get("structured_output"))
    except (ValueError, LookupError, TypeError, AttributeError) as e:
        said = f": {done.stderr.strip()}" if done.stderr.strip() else ""
        printed = tail(io.BytesIO(done.stdout.encode()))
        raise HarnessError(f"Claude Code ended with code {done.returncode} and no result to read{said}{printed}") from e


def _result(printed: str) -> dict[str, Any]:
    """The last line of `printed` holding a JSON object of type `result`, whatever follows it,
    the lines split on `\\n` alone: splitlines would split in a string. Raises `LookupError`
    when no line does."""
    for line in reversed(printed.split("\n")):
        try:
            found = json.loads(line)
        except (ValueError, RecursionError):  # a line of text, or nested too deep to be a result
            continue
        if isinstance(found, dict) and found.get("type") == "result":
            return found
    raise LookupError("no line of type result")


def _action(denial: dict[str, Any]) -> str:
    """A refused action as `Tool(what)`, what being the first value of the tool's input: the
    command of a `Bash`, the path of an `Edit`."""
    return f"{denial['tool_name']}({next(iter(denial['tool_input'].values()), '')})"
