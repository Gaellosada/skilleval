"""Claude Code, run headless: what the harness `user_local` runs. Each task is one run of
`claude --print` in the workspace, the task on its standard input, the next one resuming
the session of the one before."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from skilleval.evaluation.harness.base import (
    HarnessError,
    Reply,
    Request,
    named,
    skill_name,
)

PERMISSIONS = {
    # what would ask is refused, no one being there to answer
    "always_ask": ["--permission-mode", "manual", "--permission-prompts", "none"],
    "bypass": ["--permission-mode", "bypassPermissions"],
}
SKILLS = Path(".claude", "skills")  # where Claude Code looks for the skills of a project
TOKENS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")


def ask(request: Request) -> Reply:
    """Run Claude Code on the task of `request` and read its reply. The dollar limit stops it
    mid-task. Raises `HarnessError`."""
    setup, previous = request.setup, request.previous
    command = ["claude", "--print", "--output-format", "json", "--model", request.model]
    command += PERMISSIONS[setup.permissions]
    if request.system_prompt is not None:
        flag = "--system-prompt" if setup.override_system_prompt else "--append-system-prompt"
        command += [flag, request.system_prompt]
    if request.max_budget_usd is not None:  # Claude Code counts what one run spends
        command += ["--max-budget-usd", str(request.max_budget_usd - (previous.cost_usd if previous else 0))]
    if previous is not None:
        command += ["--resume", previous.conversation]
    try:
        if previous is None and setup.skills:
            _add_skills(setup.skills, request.folder)
        # ponytail: max_tokens is checked by the caller once the task ends, Claude Code having no
        # such limit; to stop mid-task, read --output-format stream-json and count as it goes
        done = subprocess.run(command, input=request.task, cwd=request.folder, capture_output=True, text=True)
    except OSError as e:
        raise HarnessError(f"cannot run Claude Code, which the harness user_local is: {e}") from e
    return _reply(done)


def _add_skills(skills: tuple[Path, ...], folder: Path) -> None:
    """Copy `skills` into the workspace `folder`, where Claude Code finds them beside its own:
    those of the user's configuration and those the workspace holds. Raises `HarnessError`
    for one named as one of these, `OSError` when the copy fails."""
    configuration = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    own = {
        skill_name(skill): skill
        for holder in (configuration / "skills", folder / SKILLS)
        for skill in sorted(holder.glob("*/"))
        if (skill / "SKILL.md").is_file()
    }
    for name, skill in named(skills, own).items():
        shutil.copytree(skill, folder / SKILLS / name)


def _reply(done: subprocess.CompletedProcess[str]) -> Reply:
    """The reply in the JSON result a run printed. A run stopped at the dollar limit is a
    reply, which counts more than the limit; any other that failed is a `HarnessError`."""
    try:
        result = json.loads(done.stdout)
        tokens = sum(used[kind] for used in result["modelUsage"].values() for kind in TOKENS)
        text, cost, denials = result.get("result") or "", result["total_cost_usd"], result["permission_denials"]
        reply = Reply(text, result["session_id"], tokens, cost, _action(denials[0]) if denials else None)
        failed = result["is_error"] and result["subtype"] != "error_max_budget_usd"
    except (ValueError, LookupError, TypeError, AttributeError) as e:
        said = (done.stderr + done.stdout).strip()
        raise HarnessError(f"Claude Code ended with code {done.returncode} and no result: {said}") from e
    if failed:
        raise HarnessError(f"Claude Code failed: {text or '; '.join(result.get('errors') or [result['subtype']])}")
    return reply


def _action(denial: dict[str, Any]) -> str:
    """A refused action as `Tool(what)`, what being the first value of the tool's input: the
    command of a `Bash`, the path of an `Edit`."""
    return f"{denial['tool_name']}({next(iter(denial['tool_input'].values()), '')})"
