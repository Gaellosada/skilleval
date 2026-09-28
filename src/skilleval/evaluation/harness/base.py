"""What every harness shares: the task it is given, the reply it gives, the error it raises,
the names of the skills it adds."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from skilleval.static.prompt import PromptError, read_text
from skilleval.testfile import Setup


class HarnessError(Exception):
    """What keeps a test from running properly, its case reporting `ERROR`: the harness
    missing or crashing, a model it does not know, a credential it lacks, a system prompt
    file that cannot be read, a skill-name clash, a workspace that cannot be filled."""


@dataclass(frozen=True)
class Reply:
    """What a task left, as the harness reports it. `text` is the model's final message.
    `conversation` is what the harness continues it by. `tokens` and `cost_usd` count the
    whole conversation so far. `denied` names the first action the harness refused, for want
    of a permission; None when it refused none."""

    text: str
    conversation: str
    tokens: int
    cost_usd: float
    denied: str | None = None


@dataclass(frozen=True)
class Request:
    """One task as a harness receives it: what `ask` was given, and `system_prompt`, the text
    of the system prompt `setup` holds, read from its file; None when it holds none."""

    task: str
    setup: Setup
    model: str
    folder: Path
    previous: Reply | None
    max_tokens: int | None
    max_budget_usd: float | None
    system_prompt: str | None


def skill_name(skill: Path) -> str:
    """The name of the skill in the directory `skill`: the `name` in the frontmatter of its
    `SKILL.md`, and the name of the directory when it writes none. Raises `HarnessError` for
    a `SKILL.md` that cannot be read, and for a name that cannot name a folder, which a
    harness may do with it."""
    try:
        lines = read_text(skill / "SKILL.md").splitlines()
        closing = lines.index("---", 1) if lines[:1] == ["---"] and "---" in lines[1:] else 0
        frontmatter = yaml.safe_load("\n".join(lines[1:closing]))
    except (PromptError, yaml.YAMLError) as e:
        raise HarnessError(f"cannot read the name of the skill {skill}: {e}") from e
    name = frontmatter.get("name", skill.name) if isinstance(frontmatter, dict) else skill.name
    if not isinstance(name, str) or not name.isprintable() or name in ("", "..") or Path(name).name != name:
        raise HarnessError(f"the skill {skill} is named {name!r} in its SKILL.md; a name is text that can "
                           "name a folder, with no / in it, quoted when YAML reads it as another type")
    return name


def named(skills: Iterable[Path], taken: Mapping[str, Path]) -> dict[str, Path]:
    """The skill directories `skills`, each under its `skill_name`. Raises `HarnessError` for
    a name that another of them has, or one of `taken`, the skills already there: the error
    names the skill and both directories."""
    found: dict[str, Path] = {}
    for skill in skills:
        name = skill_name(skill)
        other = found.get(name) or taken.get(name)
        if other is not None:
            raise HarnessError(f"two skills are named {name}, {other} and {skill}; rename one of them")
        found[name] = skill
    return found
