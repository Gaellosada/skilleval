"""The harness: what runs the model on a task. Specified in specs/evaluations.md, under Setup."""

from dataclasses import dataclass
from pathlib import Path

from skilleval.testfile import Setup


class HarnessError(Exception):
    """What keeps a test from running properly, its case reporting `ERROR`: the harness
    missing or crashing, a model it does not know, a credential it lacks, a system prompt
    file that cannot be read, a skill-name clash, a workspace that cannot be filled."""


@dataclass(frozen=True)
class Reply:
    """What a task left, as the harness reports it. `text` is the model's final message.
    `conversation` is what the harness continues it by. `tokens` and `cost_usd` count the
    whole conversation so far. `denied` names the action that needed permission, where the
    task stopped; None when it ran to its end."""

    text: str
    conversation: str
    tokens: int
    cost_usd: float
    denied: str | None = None


def ask(
    task: str, setup: Setup, model: str, folder: Path, previous: Reply | None = None,
    *, max_tokens: int | None = None, max_budget_usd: float | None = None,
) -> Reply:
    """Give `task` to the harness of `setup`, as written, and wait for the reply. It is all
    the harness is given of the test: what the task is checked against never comes here.

    The harness runs unattended in the workspace `folder`, with `model` and the system
    prompt, permissions and added skills of `setup`. It continues the conversation of
    `previous`, the reply to the task before.

    `max_tokens` and `max_budget_usd` are the limits of the whole test, which `previous` has
    used a part of. The harness is stopped once the conversation is past one, and the reply
    then counts more than that limit; a reply within both is of a task that ran to its end.

    Raises `HarnessError`. A skill of `setup.skills` with the name of another of them, or of
    one of the harness's own, is one: the error names the skill and both places it comes
    from. A clash within `setup.skills` is found before the harness is looked for.
    """
    raise NotImplementedError
