"""The shape of a loaded test file, and the error for one that cannot be used. Spec: specs/README.md."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


class LoadError(Exception):
    """A file that cannot be used. `str(e)` reads `<path>: <key>: <message>`, or
    `<path>: <message>` when the error is the whole file (unreadable, not a mapping).

    `key` is the dotted location inside the file (`tests.skills.constraints[1].words.max`,
    `tests.skills.kind`, `templates.house_style`), empty for the whole file; `message` names
    the offending value and what to fix.
    """

    def __init__(self, path: Path, key: str, message: str) -> None:
        super().__init__(f"{path}: {key}: {message}" if key else f"{path}: {message}")
        self.path, self.key, self.message = path, key, message


def at(key: str, part: str | int) -> str:
    """The dotted key one level below `key`: `tests.skills` under `tests`, `needs[1]` under `needs`."""
    if type(part) is int:
        return f"{key}[{part}]"
    return f"{key}.{part}" if key else str(part)


Severity = Literal["error", "warn"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]  # the levels of Claude Code, least first
Harness = Literal["user_local", "blank"]
Answer = Literal["YES", "NO"]  # what a `judge` block can require


@dataclass(frozen=True)
class Check:
    """One check entry with its parameters normalised.

    A `contains*` or `matches*` constraint is an instance: two `contains` entries are two
    checks. A format is identified by its family, any other check by its name: the test's
    entry replaces or merges with a template's, as specs/templates.md says under Merging.

    `severity` is as written; None when the entry wrote none, which runs as `error` and,
    on a constraint merged over a template's entry, keeps the template's.

    `params` holds what the entry wrote, validated and normalised, and the defaults named here:
    - a bound (`min`/`max` on `words`, `lines`, `count`, `occurrences`) is always
      `{"min": int | None, "max": int | None}`; `occurrences: 4` becomes min 4, max 4, and
      `occurrences` on `contains`, `contains_any`, `matches`, `matches_any` defaults to
      `{"min": 1, "max": None}`;
    - `words` and `patterns` are always lists of strings, read from the file when given as a
      path; `contains: Usage` becomes `{"words": ["Usage"], ...}`; `case_sensitive` on the
      `contains*` checks defaults to False; every pattern compiles, and is compiled again
      with `re.MULTILINE` when the check runs;
    - `except` is always a list;
    - lint and format checks have no parameters: `{}`.
    """

    name: str
    params: dict[str, Any] = field(default_factory=dict)
    severity: Severity | None = None


@dataclass(frozen=True)
class TextPrompt:
    """`prompt: <string>` — an inline prompt with no file behind it."""

    text: str


@dataclass(frozen=True)
class FilePrompt:
    """`prompt: {file: <path>}` — one file, resolved, never globbed."""

    path: Path


@dataclass(frozen=True)
class GlobPrompt:
    """`prompt: {include, exclude}` — `include` globbed from `base` with `Path.glob` semantics
    (`**` crosses dot-directories, and a trailing `**` matches every file below); each match's
    path relative to `base` is filtered by the `exclude` globs of `paths.glob_to_regex`."""

    base: Path
    include: str
    exclude: tuple[str, ...] = ()


PromptSpec = TextPrompt | FilePrompt | GlobPrompt


@dataclass(frozen=True)
class Setup:
    """The `setup` of an evaluation: what the model runs in. Spec: specs/evaluations.md, Setup.

    `effort` is how much the model thinks, `high` unless written. The two system prompts are
    exclusive; a `FilePrompt` is read when the test runs. `skills` are skill directories, each
    holding a `SKILL.md`. `working_folder` is the directory the workspace is filled from, None
    for a workspace starting empty.
    """

    harness: Harness
    permissions: Literal["always_ask", "bypass"] = "always_ask"
    effort: Effort = "high"
    override_system_prompt: TextPrompt | FilePrompt | None = None
    append_system_prompt: TextPrompt | FilePrompt | None = None
    skills: tuple[Path, ...] = ()
    working_folder: Path | None = None


@dataclass(frozen=True)
class Expectation:
    """The `expect` blocks on one thing a task leaves: its reply when `with_path` is None,
    otherwise the file at `with_path`, relative to the workspace, which must exist.

    `checks` are constraints, each with the severity its entry wrote or else its own
    block's. `severity` is that of the file's existence: `warn` when every block naming the
    file says so, in the test and its templates alike, otherwise None, which counts as
    `error`. A reply has no existence to check: always None.
    """

    with_path: str | None = None
    checks: tuple[Check, ...] = ()
    severity: Literal["warn"] | None = None


@dataclass(frozen=True)
class Run:
    """An `expect` block's `run`: `command`, run by bash in a copy of the workspace, passes on
    exit 0. `directory` is that of the file declaring the block, absolute, which the command
    is told as `SKILLEVAL_FILE_DIR`. `timeout` is in seconds; `severity` is as written, None
    counting as `error`."""

    command: str
    directory: Path
    timeout: float = 600
    severity: Severity | None = None


@dataclass(frozen=True)
class Judge:
    """An `expect` block's `judge`: `question`, a closed one, put to a model that answers YES,
    NO or UNKNOWN, the block passing on `require`. Spec: specs/evaluations.md, The judge.

    The judge is given the task and the reply unless `can_see_task` and `can_see_response`
    say otherwise, and the files at `files`, each relative to the workspace. `model`,
    `effort`, `harness` and the two limits, those of this judge alone, are as the block
    writes them, or else the `judge_defaults` of its file, or else the defaults here; a
    `harness` of None is that of the test's setup. `severity` is as written, None counting as
    `error`."""

    question: str
    require: Answer
    files: tuple[str, ...] = ()
    can_see_task: bool = True
    can_see_response: bool = True
    model: str = "claude-sonnet-5-5"
    effort: Effort = "high"
    harness: Harness | None = None
    max_tokens: int = 100_000
    max_budget_usd: float = 1
    severity: Severity | None = None


@dataclass(frozen=True)
class Usage:
    """An `expect` block's `usage`: the most seconds the task may take and the most tokens
    the model may write for it, at least one of the two set, None being no bound. A task
    exactly at a bound is within it. `severity` is as written, None counting as `error`."""

    max_seconds: float | None = None
    max_output_tokens: int | None = None
    severity: Severity | None = None


Block = Expectation | Run | Judge | Usage  # one block of an `expect`


@dataclass(frozen=True)
class Task:
    """One task of the chain: `text` is given to the model as written, `expect` holds what is
    checked once the task is done, in the order written: one `Expectation` per thing checked,
    and every `Run`, every `Judge` and every `Usage` on its own."""

    text: str
    expect: tuple[Block, ...] = ()


@dataclass(frozen=True)
class Evaluation:
    """The evaluation keys of a test, templates merged in. Spec: specs/evaluations.md.

    `tasks` is the chain, never empty: the templates' tasks in `uses` order, then the test's
    own. A limit covers the whole test; None is no limit.
    """

    setup: Setup
    model: str
    tasks: tuple[Task, ...]
    max_tokens: int | None = None
    max_budget_usd: float | None = None


@dataclass(frozen=True)
class Test:
    """One entry of `tests`, templates merged in.

    A static-check has a `prompt` and `checks`: lint, format and constraints in that order,
    template entries before the test's own, file order within each. An evaluation has an
    `evaluation` and neither of them.
    """

    id: str
    kind: str
    prompt: PromptSpec | None = None
    needs: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()
    evaluation: Evaluation | None = None


@dataclass(frozen=True)
class TestFile:
    """A loaded file. `root` is the resolved project root, None when the file declares none.

    `tests` keeps file order except that a needed test is pulled up to just before the first
    test that needs it. A template-only file has no tests.
    """

    path: Path
    root: Path | None
    tests: dict[str, Test]
