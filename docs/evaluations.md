# Evaluations

An `evaluation` test runs a setup on a task and checks the result: the model's reply and the files it leaves. It costs tokens, so gate it with [`needs`](test-file.md#needs) on the static checks of what it uses.

The model never knows it is being evaluated. It is given the task as written and nothing else of the test: no id, no `expect`, no mention of skilleval, in its prompt or in its workspace.

```yaml
tests:
  refactor-skill:
    kind: evaluation
    setup:
      harness: user_local
      permissions: bypass
      working_folder: ./fixtures/refactor
    model: claude-sonnet-5
    task: Split utils.py into one module per concern.
    expect:
      - response:
          - contains_none: ["I cannot"]
      - file:
          with_path: utils/strings.py
          lines:
            max: 200
    max_budget_usd: 5
```

An evaluation takes `setup`, `model`, `task`, `expect`, `max_tokens` and `max_budget_usd`, beside `kind`, `needs` and `uses`. A template can bring any of them; how they combine is in [templates.md](templates.md#evaluations). It has one case, addressed by `file::id`.

## `model`

Required, in the test or a template it uses. The model to run, as the harness names it: `claude-sonnet-5`. One string, not blank.

## `task`

Required, in the test or a template it uses. What the model is asked: a string, given to it as written, as a user would type it. Inline only, not blank.

A template's task and the test's chain: they run one after the other, in the same workspace and the same conversation.

## `max_tokens`

Optional. The most tokens the whole test may use, a positive integer: `max_tokens: 200000`. Every token counts: those read, written and cached, of every model, the harness's own system prompt included.

## `max_budget_usd`

Optional. The most the whole test may spend, in US dollars, a positive number: `max_budget_usd: 0.5`.

The two limits are independent. A test that uses exactly a limit is within it. One that goes above fails, with a finding named after the limit that says what was used, as `max_tokens: 250000 used, above the maximum of 200000`: the `expect` of the task under way is not checked and no further task runs. `max_budget_usd` stops the task under way; `max_tokens` is counted once a task ends, so a task can go past it before the test stops.

## `setup`

Required, in the test or a template it uses. What the model runs in: a mapping of the keys below, as `setup: {harness: user_local, permissions: bypass}`. Any other key is a load error.

### `harness`

Required, in the test or a template it uses. What runs the model.

- `user_local`: the harness of the user running the test, as they installed and set it up, run unattended. Today it is Claude Code, the `claude` program on the `PATH`, run as `claude --print --output-format stream-json --verbose` in the workspace, one run per task, the task on its standard input, each run after the first resuming the conversation. The user's settings, skills and servers apply as when they start it themselves, and so does any configuration the workspace holds; the test's `model`, `effort`, system prompt and `permissions` take precedence.
- `blank`: the same harness with nothing of the user's: none of their settings, skills, servers, plugins or memory, and nothing a run before left. It has the `model`, `effort`, system prompt, `permissions` and `skills` of the test, and the configuration the workspace holds, such as a `CLAUDE.md` that [`working_folder`](#working_folder) brings, so the same test runs in the same setup for two users, within the limits below. It logs in with the [`CLAUDE_CODE_OAUTH_TOKEN`](config.md#claude_code_oauth_token) of the settings: without one the test is `ERROR`.

  Claude Code runs with `CLAUDE_CONFIG_DIR` naming an empty directory, `CLAUDE_CODE_OAUTH_TOKEN` holding the token, `CLAUDE_CODE_EFFORT_LEVEL` the [`effort`](#effort), and no other variable of the environment whose name starts with `ANTHROPIC_` or `CLAUDE`: a setting of the user's, or a login that it would use over the token, such as `ANTHROPIC_API_KEY`. The directory is the user's alone to read, in the system's temporary directory, under a name that says nothing of skilleval or of the test: one per test, emptied when the test starts, shared by the tasks of its chain, and left there until the test runs again. What stays is listed in [limits.md](limits.md#harness-blank): the shell startup files and the rest of the home directory, the rest of the environment, what Claude Code builds in and what an administrator manages.

### `permissions`

Optional. How the harness treats an action that needs permission, such as editing a file or running a command.

- `always_ask`, the default: the harness asks, and no one is there to answer, so it refuses. What needs no permission goes ahead, such as reading the files of the workspace. The first action refused fails the test, with a `permissions` finding naming it, and the `expect` of that task is not checked; the next task of the chain still runs. A rule of the user's or the workspace's settings that allows an action still allows it.
- `bypass`: nothing is asked, everything is allowed but what a rule of the user's or the workspace's settings denies. An action a rule denies fails the test as under `always_ask`. What the model does runs on the user's machine with the user's rights, reading its environment included, which under `blank` holds the token: only the workspace is a copy.

### `effort`

Optional. How much effort the model puts into each task: how far it thinks, and so how many tokens it spends. One of five levels, from least to most: `low`, `medium`, `high`, `xhigh` and `max`, written in lower case; any other value is a load error. Without it, `high`, the default of the Claude API. A small task can save tokens with `setup: {harness: blank, effort: low}`.

skilleval gives it to Claude Code in `CLAUDE_CODE_EFFORT_LEVEL`, a variable of the run's environment that Claude Code puts above `--effort` and its settings, so the effort the user set up never applies, not even under `user_local`. A maximum effort set elsewhere still caps it, a hook can replace it, a model without the level runs at a lower one, and a model without effort runs without one: see [limits.md](limits.md#effort).

### `override_system_prompt`

Optional. A system prompt replacing the harness's own: a string, the prompt itself, as `override_system_prompt: You review Python pull requests.`, or a mapping with `file`, the [path](test-file.md#paths) of the file holding it, as `override_system_prompt: {file: prompts/reviewer.md}`. A file that cannot be read makes the test `ERROR` when it runs.

### `append_system_prompt`

Optional. Text added to the harness's own system prompt, written as `override_system_prompt`: `append_system_prompt: Answer in French.` A setup holding both is a load error.

### `skills`

Optional. Skills added to the harness's own: one [path](test-file.md#paths) or a list, each the directory holding a skill's `SKILL.md`, taken literally, as `skills: [.claude/skills/refactor, ./fixtures/skills/deploy]`. A path that is not such a directory, or that names a folder inside a `.skilleval` folder, is a load error.

A skill is named by the `name` in the frontmatter of its `SKILL.md`, or by its directory when it writes none. The harness's own are named by their directories: those under `skills` in the user's configuration directory, `CLAUDE_CONFIG_DIR` or else `~/.claude`, under `user_local` alone, and those under `.claude/skills` in the workspace. The name is text that can name a folder: one holding a `/`, an empty `name:`, or one that YAML reads as another type until quoted, makes the test `ERROR`. Two skills of one name, in the list or between the list and the harness's own, make the test `ERROR`, naming the skill and both directories. The skills are copied into the workspace, each under `.claude/skills/<name>`, without anything named `.skilleval`, as for [`working_folder`](#working_folder).

### `working_folder`

Optional. The [path](test-file.md#paths) of the directory the workspace is filled from, as `working_folder: ./fixtures/refactor`; without it the workspace starts empty. A path that is not a directory, or that names a `.skilleval` folder or a folder inside one, is a load error, and so is a directory holding the file that names it, test file or template file, which the model would then read. The directory itself is never modified.

## Workspace

The folder the model works in: a copy of `working_folder`, a symbolic link copied as a link and nothing named `.skilleval` copied at all, in the system's temporary directory, outside the project. Its name says nothing of skilleval or of the test. The same test always gets the same folder.

When a test starts, its workspace is emptied and filled again. The tasks of the chain share it and `expect` reads it.

## Results

When a test ends, whatever the outcome, its results go into the project, to `.skilleval/results/<test file>/<id>/` under the project root, the test file's path taken from the root, as `.skilleval/results/evals/skills.eval.yml/refactor-skill/`; in a file without `root`, under the test file's own directory, as `evals/.skilleval/results/skills.eval.yml/refactor-skill/`. The id is written as is, except that `%`, `/`, `\` and NUL are percent-encoded, and the empty id, `.` and `..` become `%`, `%2E` and `%2E%2E`, so that each test has its own folder and none climbs out: `a/b` is `a%2Fb`, `é` stays `é`. On a filesystem that ignores case, ids that differ only by case share a folder. The folder holds:

- `workspace/`: the workspace, moved there as the test left it.
- `conversation.jsonl`: every task that returned, in order, one JSON object per line: the task as a user message, `{"type": "user", "message": {"role": "user", "content": "<task>"}}`, then every line the harness printed for it.

They stay for inspection until the test runs again, which replaces the test's folder whole, anything else in it included, and leaves every other test's alone. A skipped test touches no results. A symbolic link in the workspace that points into it by an absolute path still points at the temporary folder after the move. `.skilleval/` is skilleval's own, the [settings](config.md) aside: it writes `.skilleval/.gitignore` holding `*`, so git ignores it, discovery skips it as a dot-directory, and an [`include`](test-file.md#include) never matches a file inside it, even when the glob names it.

## `expect`

Optional. What the result of the task must satisfy: a list of blocks, each a mapping holding `response` or `file`. It is checked once the task is done. Without it, a test passes when every task runs to its end within the limits, no action refused.

### `response`

The model's final message for the task. A list of [constraint](checks.md#constraints) entries, written and counted as in a static check. It reads the text of the reply and never the workspace: `contains: utils.py` asserts that the reply mentions the file, not that the file exists.

### `file`

One file the task left in the workspace. A mapping holding `with_path` and, beside it, the checks: each [constraint](checks.md#constraints) name as a key, with its parameters. A name appears once in a block; a second entry of the same name goes in a second block for the same path.

The file has to exist, as UTF-8 text: one that does not is a finding named `file`, and the checks of the block are skipped.

### `with_path`

Required in a `file` block. The path of the file, relative to the workspace, naming one file and never a glob: `with_path: utils/strings.py`. A path starting with `./`, an absolute one, one naming the workspace itself, as `.`, or one climbing out of the workspace with `..` is a load error. The path is normalised: `a/../b.md` is `b.md`.

### `severity`

`error`, the default, or `warn`, at two levels. Beside `response`, as `{response: [{words: {max: 300}}], severity: warn}`, or beside `with_path`, as `file: {with_path: NOTES.md, severity: warn}`, it covers the whole block, the existence of the file included. On one check, as `words: {max: 300, severity: warn}`, it covers that check and wins over the block's. A `severity` beside `file`, rather than inside it, is a load error. Where several blocks name the same file, the file has to exist at `error` unless every one of them says `warn`.

A word or pattern list given as a path resolves from the file declaring it, test file or template file, like any other [path](test-file.md#paths) there, never from the workspace.

## Report

A failing check fails the test, as do a permission request and a limit; the next task of the chain still runs unless a limit stopped the test. A test that could not run properly is `ERROR` and stops there, reporting its reason alone: [settings](config.md) that cannot be read or lack a credential, the harness missing or failing, a model it does not know, a system prompt file that cannot be read, a `SKILL.md` that cannot be read, whose frontmatter is not valid YAML or whose name cannot name a folder, a skill named twice or that cannot be copied, a workspace that cannot be filled, [results](#results) that cannot be kept, unless the test already stopped on another of these, which it then reports.

A finding names what it is about before the check: `response`, or the file's `with_path`. When more than one task ran, the position of the task comes first, as in `task 2: response: words: ...`. What is not a check reports under the name of its key: `file`, `permissions`, `max_tokens`, `max_budget_usd`. The workspace kept follows, as `workspace: <path>`; `conversation.jsonl` sits beside it (see [Results](#results)).

## skilleval's own suite

`pytest` never runs Claude Code, so it spends no tokens and needs no login, and it does not test an evaluation end to end. It points `PATH`, `CLAUDE_CONFIG_DIR` and the system's temporary directory at directories of its own, and unsets the credentials of the [settings](config.md). The tests that run an evaluation put a stand-in in place of the harness. The tests of `user_local` and `blank` put a stand-in `claude` program on the `PATH`, which records the command and the environment it is given and prints JSON lines ending with a result the test sets. What they pin is the command skilleval builds, the skills it copies into the workspace, and how it reads the result and the lines before it. They do not pin that the installed Claude Code accepts that command, prints that result, or keeps to the behaviours above: permissions, effort, skills, limits. Check those by running an evaluation with `skilleval`, which does spend tokens.
