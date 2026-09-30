# Evaluations

An evaluation runs a setup on a task and checks the result: the model's reply and the files it leaves. It is a `kind: evaluation` test, declared under `tests` like any other and addressed by the same node ids; the test file itself is described in [README.md](README.md).

> **Important — the model never knows it is being evaluated.** It sees the task, as a user would give it, and nothing of the evaluation around it: no test id, no grading criteria, no expected answer, no mention of skilleval, in its prompt, its workspace or anything else it can read. A model that knows it is tested behaves differently, and the result would measure that instead of the setup.

```yaml
tests:
  refactor-skill:
    kind: evaluation
    setup:
      harness: user_local
      permissions: bypass
      effort: medium
      override_system_prompt:
        file: prompts/reviewer.md
      working_folder: ./fixtures/refactor
    model: claude-opus-5-5
    task: Split utils.py into one module per concern.
    expect:
      - response:
          - contains: utils            # the reply mentions utils; whether the folder exists is not checked
      - file:
          with_path: utils/strings.py  # this one is checked: it must exist
    max_tokens: 200000
    max_budget_usd: 5
```

- `task` — what the model is asked, a string given to it as written, as a user would type it. Inline only: no `file` or `include` form; an empty or blank one is a load error. A template may hold one too: its task runs before the test's, in the same workspace and conversation (see [templates.md](templates.md)). Required once templates are merged: a test with no task of its own or from a template is a load error.
- `expect` — what the result of the task must satisfy, described below.
- `setup` — what the model runs in, described below.
- `model` — the model to run, exactly one; an empty or blank one is a load error. Required once templates are merged: a test with none is a load error.
- `max_tokens` — the most tokens the whole test may use, a positive integer.
- `max_budget_usd` — the most the whole test may spend, in US dollars, a positive number.

What runs the models, and with which credentials, is not the test's to say: it is a setting of whoever runs it, read from `.skilleval/config.yml` as the test starts ([config.md](config.md)).

`max_tokens` and `max_budget_usd` are independent and both optional: either, both or neither may be set, and with neither the test runs unlimited. Whichever limit is hit first stops the test, which then fails: the task under way is left unchecked and no further task runs. A test that uses exactly a limit is within it.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors as keys of an evaluation; constraint entries have their place under `expect`. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).

## Setup

- `harness` — what runs the model. Required: a test whose setup has none once its templates are merged is a load error, as is any value other than these two:
    - `blank` — the harness as it is installed, with nothing of the user's: none of their settings, skills, servers, plugins or memory, and nothing a run before left. It has what the test gives it and no more: the `model`, `effort`, system prompt keys, `permissions` and `skills` of the test, and the configuration the workspace holds, such as a `CLAUDE.md` that `working_folder` brings. The same test therefore runs in the same setup for two users, as far as the harness allows, its limits being listed below. The user's login goes with the rest, so the harness logs in with the `CLAUDE_CODE_OAUTH_TOKEN` of the settings ([config.md](config.md)): a test run without one reports `ERROR`, naming the settings file.
    - `user_local` — the harness of the user running the test, as they have it installed and set up on their machine, run unattended: it receives each task, works until it answers, and never waits for a person. Whatever that user has set up — settings, skills, servers — applies as when they start it themselves, so the same test can behave differently for two users. It works in the workspace, so any configuration the workspace holds applies too. The test's `model`, `effort`, system prompt keys and `permissions` take precedence over that configuration.
- `permissions` — how the harness treats an action that needs permission, such as editing a file or running a command. One of two:
    - `always_ask` — the harness asks for every permission, ignoring what the user's configuration allows: only what it does unasked on a fresh install goes ahead, such as reading the files of its working directory. No one is there to answer, so the first request fails the test, the finding naming the action; the task stops there and its `expect` is not checked, and the next task in the chain still runs.
    - `bypass` — every permission is bypassed: nothing is ever asked, everything is allowed.

  Optional: without it, `always_ask`, the lower of the two. Under `bypass`, whatever the model does runs on the user's machine with the user's rights: only the workspace is a copy. That includes reading its own environment, which with `blank` holds the token.
- `effort` — how much effort the model puts into each task: how far it thinks and how many tokens it spends on the way. One of five, from least to most: `low`, `medium`, `high`, `xhigh`, `max`, written as is; any other value is a load error. Optional: without it, `high`, the Claude API's own default. The harness is always given one, so the effort the user set up never applies, with `user_local` either, as far as the harness allows. A model that does not support the level, or effort at all, runs as the harness has it.
- `override_system_prompt` — a system prompt replacing the harness's own. Written as for a static check's `prompt`: a string, the system prompt itself inline, or a mapping with `file`, the path to the file holding it; the `include` form is an error, since a setup has one system prompt. A file that cannot be read is found when the test runs, which reports `ERROR`. Optional: without it the harness keeps its own.
- `append_system_prompt` — text appended to the harness's own system prompt, which otherwise stays in place. Written as `override_system_prompt`, `include` form excluded.

  The two are exclusive: a test whose setup has both once its templates are merged is a load error. Neither is required.
- `skills` — skills added to the harness's own, one path or a list. Each path is a skill's directory, the one holding its `SKILL.md`, and resolves like any other path: `./` from the test file, absolute as is, anything else from the project root. It is taken literally, never globbed; a path that is not a directory, a directory with no `SKILL.md` directly inside, or a path that names a folder inside a `.skilleval` folder, as for `working_folder`, is a load error. The skills are appended, never substituted: with `user_local`, the harness runs with every skill the user has plus these; with `blank`, with those built into it plus these. A skill's name is the `name` in the frontmatter of its `SKILL.md`. A skill whose name one of the harness's own skills already has, or another in the list, is found only when the test runs: the test reports `ERROR`, naming the skill and both places it comes from. Optional: without it the harness has only its own. Appending is to the harness; between a template and a test the list is replaced like any other `setup` key, never joined (see [templates.md](templates.md)).
- `working_folder` — the initial contents of the workspace, not where the model works. The model works in the **workspace**, a folder skilleval clones from `working_folder` when the test starts, so the folder itself is never modified and every run starts from the same contents. A symbolic link in it is copied as a link, never followed. A folder or a file named `.skilleval` in it, at any depth, is not copied: it is skilleval's, its results would tell the model that the folder was tested, and its settings can hold credentials. For the same reason a `working_folder` whose path, as written, names a `.skilleval` folder or a folder inside one is a load error; a project that itself lives below a folder of that name is not concerned. A path that is not a directory is a load error, and so is a directory holding the file that names it, test file or template file, which the model would then read. Optional: without it the workspace starts empty.

  The workspace lives outside the project, in the system's temporary directory, under a folder skilleval creates and uses alone, with one folder per test; nothing to set up or configure. Being outside the project, the harness picks up none of the project's `CLAUDE.md` files, and no test file sits next to the model's work. The names are neutral, since the model can read its own working directory: neither the folder nor its parent says anything of skilleval or of the test. The same test always gets the same folder.

  When a test starts, its workspace is emptied and filled again from `working_folder`. It is shared by the test's chained tasks and read by its `expect`. Once the test ends, whatever the outcome, an error mid-chain included, its results go into the project, where the model never worked: to `<base>/.skilleval/results/<test file relative to base>/<id>/`, `<base>` being the project root, or the test file's directory in a file without `root`, and the id written as is, except that `%`, `/`, `\` and NUL are percent-encoded, and the empty id, `.` and `..` become `%`, `%2E` and `%2E%2E`, into one folder name of its own — `refactor-skill` and `é` stay as they are, while no id climbs out or shares a folder. On a filesystem that ignores case, ids that differ only by case share a folder. There `workspace/` is the workspace, moved as the test left it, and `conversation.jsonl` holds every task that returned, in order, one JSON object per line: the task as a user message, `{"type": "user", "message": {"role": "user", "content": <task>}}`, then every line the harness printed for it. Both stay for inspection until the test runs again, and skilleval prints the path of `workspace/` under a failure or an error, and with `-v` under every test that ran: a skipped one touches no results. `.skilleval/` is skilleval's alone: a run replaces its test's results folder whole, and the id keeps that folder from being another test's, which stays untouched; beside it, a workspace and the configuration of a `blank` harness are the only folders skilleval ever empties. Keeping results, skilleval writes `.skilleval/.gitignore` holding `*`, as pytest does in its cache, so git ignores them. Discovery skips `.skilleval/` as any dot-directory, and an `include` never matches a file inside it, even when the glob names it ([README.md](README.md)). Results that cannot be kept are an error, unless the chain already stopped on one, which it then reports.

```yaml
setup:
  harness: user_local
  permissions: bypass                  # never asks: edits files and runs commands freely
  effort: xhigh                        # more than the default, high
  override_system_prompt:
    file: prompts/reviewer.md
  skills:
    - .claude/skills/refactor          # relative to the project root
    - ./fixtures/skills/fake-deploy    # relative to this test file
  working_folder: ./fixtures/refactor
```

```yaml
setup:
  harness: user_local
  override_system_prompt: You review Python pull requests.
```

### What the harness runs

Claude Code, the `claude` program on the `PATH`, run headless: one run per task, in the workspace, the task on its standard input, each run resuming the session of the one before. It prints JSON lines (`--output-format stream-json --verbose`), the last its result, which the reply is read from; every line goes to `conversation.jsonl`. The tokens and the cost are those Claude Code reports, which count the whole session, resumed runs included. The `effort` is given by `CLAUDE_CODE_EFFORT_LEVEL`, the variable of the run's environment that Claude Code puts above `--effort` and its settings. Checked with Claude Code 2.1.283, the JSON lines and `blank` with 2.1.284, `effort` with 2.1.285. What runs the models is the `backend` of the settings ([config.md](config.md)), `claude_cli` here: another backend is another module of `skilleval.evaluation.harness`, and nothing else of skilleval knows which one runs.

`blank` is the same program run with a configuration directory of its own, empty, in place of the user's: `CLAUDE_CONFIG_DIR` names it, `CLAUDE_CODE_OAUTH_TOKEN` holds the token of the settings, and `CLAUDE_CODE_EFFORT_LEVEL` the `effort`, as with `user_local`. Every other variable of the environment whose name starts with `ANTHROPIC_` or `CLAUDE` is taken out of the run's: a setting among them would be the user's, and a login, such as `ANTHROPIC_API_KEY`, would be used over the token and billed without a word. The directory is the user's alone to read, and in the system's temporary directory, beside the workspaces and named as they are, saying nothing of skilleval or of the test, since the model can read its path: Claude Code tells it where its memory is kept, inside that directory. Each test has its own, the same every time, emptied when the test starts and shared by its chained tasks, each resuming a session kept there; it stays, with those sessions, until the test runs again.

Where Claude Code cannot do what this spec says, for now:

- `always_ask` — Claude Code refuses what would ask and tells the model so, which carries on: the task runs to its end, and the test then fails on the first request, the `expect` of the task unchecked. The permission mode the user configured is overridden; a rule of their settings, or of the workspace's, that allows an action still allows it. One that denies an action refuses it under `bypass` too, and the test fails the same way.
- `max_tokens` — Claude Code has no such limit, so the tokens are counted once a task ends: a task can go past the limit before the test stops. `max_budget_usd` stops it mid-task: each run is given what the runs before it left of the budget. The tokens are those of every model the conversation used: read, written, and read from or written to the cache.
- `blank` — what Claude Code builds in stays, its own skills and agents, and so do the settings an administrator manages, on the machine or for the account the token logs in, which no directory replaces. So does the rest of the environment, the machine's, such as `PATH`, `HOME` and the proxy variables, which the run needs; what Claude Code reads there under another name than the two prefixes, such as `MAX_THINKING_TOKENS` or `DISABLE_PROMPT_CACHING`, stays as the user set it. So do the shell startup files: Claude Code builds the shell of its Bash tool from the startup file of the user's shell, `~/.bashrc` for bash and `~/.zshrc` for zsh, whose aliases, functions and shell options reach the model's commands, its exported variables aside; seen with 2.1.285 and bash. And so does the rest of the home directory, such as the user's git identity, `HOME` being passed as it is.
- `effort` — a maximum effort caps it: one in the settings of the user, with `user_local`, or of an administrator, and one the account's organization sets for the model. Above the maximum, Claude Code runs the task at the maximum; read from its program, 2.1.285, and its documentation.
- `skills` — copied into the workspace when the test starts, each under `.claude/skills/<name>`, where the model and `expect` can see them, without anything named `.skilleval`, as for `working_folder`: a skill tested by a file beside its `SKILL.md` holds one. Claude Code names a skill after its directory, so an added skill is listed under the `name` of its frontmatter, which has to be text that can name a folder: one holding a `/`, or that YAML reads as another type until quoted, is an error when the test runs. A `SKILL.md` that names no skill is named after its directory. The harness's own skills are those of the user's configuration, the folder `CLAUDE_CONFIG_DIR` names or else `~/.claude`, with `user_local` alone, and those the workspace holds, named after their directories; a plugin's carry the plugin's name and never clash.

## Expect

Checks on the result of a task, run once the task is done and never shown to the model. `expect` is a list of blocks, as many as needed, each a mapping with one key naming what it checks, the way a workflow step is a `uses` or a `run`:

- `response` — the model's final message for the task: its last reply, not the whole conversation. Holds a list of constraint entries, written exactly as a static check's `constraints` ([static-checking.md](static-checking.md), Constraints) — same entries, parameters, shorthands and repetition — applied to that message as they would be to a prompt. Several `response` blocks read as one list.

  `response` reads only the text of the reply, never the workspace: a check naming a file or folder asserts that the reply mentions it, not that it exists or holds anything; that is what `file` is for.
- `file` — one file the task left in the workspace. Holds `with_path`, required, and beside it the checks, each constraint name as a key taking the same parameters as under `response`: `words`, `lines`, `contains*`, `matches*`, `paths`, `urls` and `code`. A key name appears once per block, so a second entry of the same name — a soft budget beside a hard one — goes in a second block for the same path.

  `with_path` is relative to the workspace the model worked in — never to `working_folder`, which only filled it at the start — and to nothing else: `./`, an absolute path and one climbing out with `..` are load errors, since nothing outside the workspace is in reach. It names one exact file, never a glob, and two spellings of one path (`a.md`, `docs/../a.md`) name the same file. The block asserts the file exists: a missing one fails with that finding and the block's checks are skipped, as does one that is not UTF-8 text. A block with `with_path` alone asserts existence and nothing more.

`severity` sets how a failure counts, `error` unless set to `warn`, at two levels. On a section it covers the whole of it, the existence of a `file` included; on one check it covers that check alone and wins over the section's. On a `file` block it sits beside `with_path`; on a `response` block beside `response`, since `response` holds a list. Where several blocks check the same thing, each one's `severity` covers its own checks, and the file has to exist at `error` unless every block naming it says `warn`, a template's blocks included: a block without `warn` always asks for the file at `error`:

```yaml
expect:
  - response:
      - contains: [qubit]
      - words:
          max: 400
          severity: error              # this check only, over the section's warn
    severity: warn                     # the whole response section
  - file:
      with_path: NOTES.md
      severity: warn                   # the whole section: existence and every check
      lines:
        max: 50
```

`lint` and `format` belong to static checks and are errors in either block, as is any key other than those above. A word or pattern list given as a path is not a workspace path: it resolves from the file declaring it, test or template, like any other path there, and never reaches the model.

```yaml
task: Explain me quantum computing.
expect:
  - response:
      - contains: [qubit, superposition]
      - contains_none: ["I cannot", "I'm unable"]
      - matches_any:
          patterns: ["(?i)entangle(d|ment)"]
      - words:
          min: 100
          max: 600
      - words:
          max: 400
          severity: warn               # a soft budget beside the hard one
      - code:
          count: {max: 0}              # prose only
```

```yaml
task: Split utils.py into one module per concern.
expect:
  - response:
      - contains_none: ["I cannot"]

  - file:
      with_path: utils/strings.py
      matches:
        patterns: ['^def slugify\(']   # single quotes keep the backslash as written
      lines:
        max: 200

  - file:
      with_path: docs/module layout.md
      contains: [utils/strings.py]     # a list: a lone string with a / would be read as a word-list file

  - file:
      with_path: utils/__init__.py     # only has to exist
```

An `expect` belongs to the task beside it: a template's is checked right after the template's task, before the next task starts, so a chain can be checked step by step. An `expect` with no task beside it — in a template holding none, or in a test whose only task comes from its templates — applies to the nearest task above it in the chain, which runs the templates' tasks in `uses` order, then the test's. One with no task above it is a load error. Where several land on the same task, their blocks join and merge as in [templates.md](templates.md).

A failing check fails the test, and so does a task that does not finish, its `expect` then left unchecked; either way the next task in the chain still runs, in the same workspace and conversation, unless a limit stopped the task: a limit stops the test. A warning never fails, as anywhere else.

The test reports `FAILED` for what the setup did or did not do: a failing check, a permission request, a limit reached. It reports `ERROR` for whatever kept it from running properly — the harness missing or crashing, a model it does not know, settings that cannot be read, a credential it lacks, a skill-name clash — and stops there: no further task runs, nothing more is checked, and the reason is all it reports, without what earlier tasks found. Findings report under the case like a static check's, prefixed with `response` or the file's `with_path` and, when more than one task ran, the task's position in the chain: `task 2: response: words: ...`. What is not a check reports the same way, under the name of its key: `file` for a file that has to exist, `permissions`, `max_tokens`, `max_budget_usd`. The workspace kept follows as `workspace: <path>`, `conversation.jsonl` beside it. `expect` is optional: without it, a test passes when every task runs to its end within the limits.

## Later

Not specified yet; to come after everything above.

- MCP servers in `setup`, appended to the harness's own the way `skills` are.
- A finer handling of permissions than failing the test on the first request the harness cannot put to anyone.
- Scripts run in the workspace after a task, under `expect`, passing or failing by their exit code: a test suite checking the code the task wrote.
- Several tasks in one test, run in sequence with assertions between them. Like a template's task before the test's, they share the workspace and the conversation, so each task builds on the last: one task writes the tests, the next implements the code that passes them.

Worked example: [examples/evaluation.eval.yml](examples/evaluation.eval.yml) and the templates it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
