"""The settings of whoever runs the tests: what runs the models, and the credentials it takes,
read from `.skilleval/config.yml`. Specified in specs/config.md."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from skilleval.evaluation import workspace
from skilleval.testfile.checks import choice, read_at
from skilleval.testfile.document import known_keys, read_document
from skilleval.testfile.schema import LoadError

NAME = "config.yml"
BACKENDS = ("claude_cli", "claude_api")
CREDENTIALS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
DEFAULT = """\
# The settings of skilleval for this project. They are yours alone: git ignores this folder.

# What runs the models: claude_cli, Claude Code run headless, or claude_api, the Claude API.
backend: claude_cli

# Credentials. One that is not written here is read from the environment variable of its name.
# ANTHROPIC_API_KEY: sk-ant-api03-...          # what the backend claude_api needs
# CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...    # what the harness blank needs; `claude setup-token` prints one
"""


@dataclass(frozen=True)
class Config:
    """The settings read from the file `path`, which an error about them names. `backend` is
    what runs the models. A credential is None when neither the file nor the environment
    holds it."""

    path: Path
    backend: Literal["claude_cli", "claude_api"] = "claude_cli"
    anthropic_api_key: str | None = None
    claude_code_oauth_token: str | None = None


def load(path: Path) -> Config:
    """The settings of the file `path`, written with `DEFAULT` first when it is missing, in a
    folder that git ignores. Raises `LoadError` for a file that cannot be read or holds what
    the spec does not allow, and `OSError` when it cannot be written."""
    if not path.exists():
        workspace.ignore(path.parent)
        path.write_text(DEFAULT, encoding="utf-8")
    written = read_document(path, holding="backend")
    known_keys(written, {"backend", *CREDENTIALS}, path, "")
    if "backend" not in written:
        raise LoadError(path, "backend", f"backend is missing; write one of {', '.join(BACKENDS)}")
    backend = read_at(choice(*BACKENDS), written["backend"], path, "backend")
    return Config(path, backend, *(_credential(written, name, path) for name in CREDENTIALS))


def _credential(written: dict[str, Any], name: str, path: Path) -> str | None:
    """The credential `name` as the file writes it, or else as the environment variable of
    its name holds it. An error never shows the value."""
    if name not in written:
        return os.environ.get(name) or None
    value = written[name]
    if not isinstance(value, str) or not value.strip():
        raise LoadError(path, name, "expected text that is not blank; remove the key to read it from the environment")
    return str(value)
