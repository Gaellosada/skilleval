"""The harness: what runs the model on a task. Specified in specs/evaluations.md, under Setup.

`ask` is what the rest of the package calls. It reads what the setup names, then hands the
task to what runs the models, the `backend` of the settings: a module of this package,
listed in `BACKENDS`, which runs the `harness` of the setup. Another backend is another
module, taking a `Request` and giving a `Reply`.
"""

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from skilleval.evaluation.config import Backend, Config
from skilleval.evaluation.harness import claude_api, claude_code
from skilleval.evaluation.harness.base import HarnessError, Reply, Request
from skilleval.static.prompt import PromptError, read_text
from skilleval.testfile import FilePrompt, Setup, TextPrompt

__all__ = ["BACKENDS", "HarnessError", "Reply", "Request", "ask"]

BACKENDS: dict[Backend, Callable[[Request], Reply]] = {"claude_cli": claude_code.ask, "claude_api": claude_api.ask}


def ask(
    task: str, setup: Setup, model: str, folder: Path, previous: Reply | None = None,
    *, config: Config, max_tokens: int | None = None, max_budget_usd: float | None = None,
    schema: dict[str, Any] | None = None,
) -> Reply:
    """Give `task` to the harness of `setup`, as written, and wait for the reply. It is all
    the harness is given of the test: what the task is checked against never comes here.

    The harness runs unattended in the workspace `folder`, with `model` and the effort,
    system prompt, permissions and added skills of `setup`, by the backend and with the
    credentials of `config`. It continues the conversation of `previous`, the reply to the
    task before.

    `max_tokens` and `max_budget_usd` are the limits of the whole test, which `previous` has
    used a part of. A harness that can be stopped is, once the conversation is past one,
    and the reply then counts more than that limit; a reply within both is of a task that
    ran to its end, an action refused or not.

    The reply's `seconds` are those of the backend's run, measured here by the wall clock,
    whatever the backend: its start-up is included, and nothing it reports of itself.

    With `schema`, a JSON schema, the task is a judge's: the harness answers with an object
    that fits it, the `output` of the reply, and runs with the login of its user and nothing
    else of theirs, neither a tool nor a settings file.

    Raises `HarnessError`. A system prompt file that cannot be read is one, naming the file.
    A skill of `setup.skills` with the name of another of them, or of one of the harness's
    own, is one, as `base.named` raises it. That file and a clash within `setup.skills` are
    found before the harness is looked for. A credential the backend or the harness needs
    and `config` lacks is one, naming the settings file, found before that clash.
    """
    system_prompt = _text(setup.override_system_prompt or setup.append_system_prompt)
    request = Request(task, setup, model, folder, previous, max_tokens, max_budget_usd, config, system_prompt, schema)
    start = time.monotonic()
    reply = BACKENDS[config.backend](request)
    # Sonar reads replace as returning any dataclass; it returns a Reply, as mypy infers
    return replace(reply, seconds=time.monotonic() - start)  # NOSONAR(S5886)


def _text(prompt: TextPrompt | FilePrompt | None) -> str | None:
    if not isinstance(prompt, FilePrompt):
        return prompt.text if prompt else None
    try:
        return read_text(prompt.path)
    except PromptError as e:
        raise HarnessError(f"cannot read the system prompt file {prompt.path}: {e}") from e
