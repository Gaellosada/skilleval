"""The settings of whoever runs the tests: what runs the models, and the credentials it takes,
read from `.skilleval/config.yml`. Specified in specs/config.md."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

import yaml

from skilleval.evaluation import workspace
from skilleval.testfile.schema import LoadError

NAME = "config.yml"
CREDENTIALS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
KEYS = ("backend", *CREDENTIALS)
DEFAULT = """\
# The settings of skilleval for this project. They are yours alone: git ignores this folder.

# What runs the models: claude_cli, Claude Code run headless, or claude_api, the Claude API.
backend: claude_cli

# Credentials. One that is not written here is read from the environment variable of its name.
# ANTHROPIC_API_KEY: sk-ant-api03-...          # what the backend claude_api needs
# CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...    # what the harness blank needs; `claude setup-token` prints one
"""

Backend = Literal["claude_cli", "claude_api"]


@dataclass(frozen=True)
class Config:
    """The settings read from the file `path`, which an error about them names. `backend` is
    what runs the models. A credential is None when neither the file nor the environment
    holds it."""

    path: Path
    backend: Backend = "claude_cli"
    anthropic_api_key: str | None = None
    claude_code_oauth_token: str | None = None


def load(path: Path) -> Config:
    """The settings of the file `path`, written with `DEFAULT` first when it is missing, its
    user's alone to read, in a folder that git ignores from then on. A credential the file
    does not write is that of the environment variable of its name, when it holds one.
    Raises `LoadError` for a file that cannot be read or holds what the spec does not allow,
    and `OSError` when it cannot be written."""
    workspace.ignore(path.parent)
    if not path.exists():
        path.touch(mode=0o600)
        path.write_text(DEFAULT, encoding="utf-8")
    written = _read(path)
    if written.get("backend") not in get_args(Backend):
        raise LoadError(path, "backend", f"expected one of {', '.join(get_args(Backend))}")
    credentials = {name.lower(): written.get(name) or os.environ.get(name, "").strip() or None for name in CREDENTIALS}
    return Config(path, cast(Backend, written["backend"]), **credentials)


def _read(path: Path) -> dict[str, str]:
    """The keys the file `path` writes, each with its text, stripped. The file holds
    credentials, so an error shows nothing of what is written: it names a key of `KEYS`, or
    else a line."""
    try:
        node = yaml.compose(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    except OSError as e:
        raise LoadError(path, "", f"cannot read the file: {e}") from e
    except UnicodeDecodeError:  # its message quotes a byte
        raise LoadError(path, "", "not UTF-8 text") from None
    except (yaml.YAMLError, RecursionError) as e:  # the message of the first quotes the line
        mark = getattr(e, "problem_mark", None)
        raise LoadError(path, "", f"not valid YAML{f', at line {mark.line + 1}' if mark else ''}") from None
    if not isinstance(node, yaml.MappingNode):
        raise LoadError(path, "", f"the file must be a mapping holding {', '.join(KEYS)}")
    written: dict[str, str] = {}
    for key, value in node.value:
        name = key.value
        if not isinstance(key, yaml.ScalarNode) or name not in KEYS:
            raise LoadError(path, "", f"unknown key at line {key.start_mark.line + 1}; the keys are {', '.join(KEYS)}")
        if name in written:
            raise LoadError(path, name, f"written a second time at line {key.start_mark.line + 1}; a key appears once")
        if not isinstance(value, yaml.ScalarNode) or value.tag != "tag:yaml.org,2002:str" or not value.value.strip():
            raise LoadError(path, name, "expected text that is not blank")
        written[name] = value.value.strip()
    return written
