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

The two limits are independent. A test that uses exactly a limit is within it. One that goes above fails, with a finding named after the limit: the `expect` of the task under way is not checked and no further task runs. `max_budget_usd` stops the task under way; `max_tokens` is counted once a task ends, so a task can go past it before the test stops.

## `setup`

Required, in the test or a template it uses. What the model runs in: a mapping of the keys below, as `setup: {harness: user_local, permissions: bypass}`. Any other key is a load error.

### `harness`

Required, in the test or a template it uses. What runs the model.

- `user_local`: the harness of the user running the test, as they installed and set it up, run unattended. Today it is Claude Code, the `claude` program on the `PATH`. The user's settings, skills and servers apply as when they start it themselves, and so does any configuration the workspace holds; the test's `model`, system prompt and `permissions` take precedence.
- `none`: the model called directly. Not supported yet: a load error.

### `permissions`

Optional. How the harness treats an action that needs permission, such as editing a file or running a command.

- `always_ask`, the default: the harness asks, and no one is there to answer, so it refuses. What needs no permission goes ahead, such as reading the files of the workspace. The first action refused fails the test, with a `permissions` finding naming it, and the `expect` of that task is not checked; the next task of the chain still runs. A rule of the user's or the workspace's settings that allows an action still allows it.
- `bypass`: nothing is asked, everything is allowed but what a rule of the user's or the workspace's settings denies. What the model does runs on the user's machine with the user's rights: only the workspace is a copy.

### `override_system_prompt`

Optional. A system prompt replacing the harness's own: a string, the prompt itself, as `override_system_prompt: You review Python pull requests.`, or a mapping with `file`, the [path](test-file.md#paths) of the file holding it, as `override_system_prompt: {file: prompts/reviewer.md}`. A file that cannot be read makes the test `ERROR` when it runs.

### `append_system_prompt`

Optional. Text added to the harness's own system prompt, written as `override_system_prompt`: `append_system_prompt: Answer in French.` A setup holding both is a load error.

### `skills`

Optional. Skills added to the harness's own: one [path](test-file.md#paths) or a list, each the directory holding a skill's `SKILL.md`, taken literally, as `skills: [.claude/skills/refactor, ./fixtures/skills/deploy]`. A path that is not such a directory is a load error.

A skill is named by the `name` in the frontmatter of its `SKILL.md`, or by its directory when it writes none; the harness's own are named by their directories. Two skills of one name, in the list or between the list and the harness's own, make the test `ERROR`, naming the skill and both directories. The skills are copied into the workspace, each under `.claude/skills/<name>`.

### `working_folder`

Optional. The [path](test-file.md#paths) of the directory the workspace is filled from, as `working_folder: ./fixtures/refactor`; without it the workspace starts empty. A path that is not a directory is a load error. The directory itself is never modified.

## Workspace

The folder the model works in: a copy of `working_folder`, a symbolic link copied as a link, in the system's temporary directory, outside the project. Its name says nothing of skilleval or of the test. The same test always gets the same folder.

When a test starts, its workspace is emptied and filled again. The tasks of the chain share it and `expect` reads it; it is then left as it is, for inspection, until the test runs again.

## `expect`

Optional. What the result of the task must satisfy: a list of blocks, each a mapping holding `response` or `file`. It is checked once the task is done. Without it, a test passes when every task runs to its end within the limits.

### `response`

The model's final message for the task. A list of [constraint](checks.md#constraints) entries, written and counted as in a static check. It reads the text of the reply and never the workspace: `contains: utils.py` asserts that the reply mentions the file, not that the file exists.

### `file`

One file the task left in the workspace. A mapping holding `with_path` and, beside it, the checks: each [constraint](checks.md#constraints) name as a key, with its parameters. A name appears once in a block; a second entry of the same name goes in a second block for the same path.

The file has to exist, as UTF-8 text: one that does not is a finding named `file`, and the checks of the block are skipped.

### `with_path`

Required in a `file` block. The path of the file, relative to the workspace, naming one file and never a glob. A path starting with `./`, an absolute one, or one climbing out of the workspace with `..` is a load error.

### `severity`

`error`, the default, or `warn`, at two levels. Beside `response`, as `{response: [{words: {max: 300}}], severity: warn}`, or beside `with_path`, as `file: {with_path: NOTES.md, severity: warn}`, it covers the whole block, the existence of the file included. On one check, as `words: {max: 300, severity: warn}`, it covers that check and wins over the block's. Where several blocks name the same file, the file has to exist at `error` unless every one of them says `warn`.

A word or pattern list given as a path resolves from the test file, like any other [path](test-file.md#paths) there, never from the workspace.

## Report

A failing check fails the test, as do a permission request and a limit; the next task of the chain still runs unless a limit stopped the test. A test that could not run properly is `ERROR` and stops there, reporting its reason alone: the harness missing or failing, a model it does not know, a system prompt file that cannot be read, a skill named twice, a workspace that cannot be filled.

A finding names what it is about before the check: `response`, or the file's `with_path`. When more than one task ran, the position of the task comes first, as in `task 2: response: words: ...`. What is not a check reports under the name of its key: `file`, `permissions`, `max_tokens`, `max_budget_usd`. The workspace follows, as `workspace: <path>`.
