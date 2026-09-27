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

`max_tokens` and `max_budget_usd` are independent and both optional: either, both or neither may be set, and with neither the test runs unlimited. Whichever limit is hit first stops the test, which then fails: the task under way is left unchecked and no further task runs. A test that uses exactly a limit is within it.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors as keys of an evaluation; constraint entries have their place under `expect`. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).

## Setup

- `harness` — what runs the model. Required: a test whose setup has none once its templates are merged is a load error, as is any value other than these two:
    - `none` — no harness; the model is called directly.
    - `user_local` — the harness of the user running the test, as they have it installed and set up on their machine, run unattended: it receives each task, works until it answers, and never waits for a person. Whatever that user has set up — settings, skills, servers — applies as when they start it themselves, so the same test can behave differently for two users. It works in the workspace, so any configuration the workspace holds applies too. The test's `model`, system prompt keys and `permissions` take precedence over that configuration.

  `none` is not supported yet: for now, a test using it is a load error saying so.
- `permissions` — how the harness treats an action that needs permission, such as editing a file or running a command. One of two:
    - `always_ask` — the harness asks for every permission, ignoring what the user's configuration allows: only what it does unasked on a fresh install goes ahead, such as reading the files of its working directory. No one is there to answer, so the first request fails the test, the finding naming the action; the task stops there and its `expect` is not checked, and the next task in the chain still runs.
    - `bypass` — every permission is bypassed: nothing is ever asked, everything is allowed.

  Optional: without it, `always_ask`, the lower of the two. Under `bypass`, whatever the model does runs on the user's machine with the user's rights: only the workspace is a copy.
- `override_system_prompt` — a system prompt replacing the harness's own. Written as for a static check's `prompt`: a string, the system prompt itself inline, or a mapping with `file`, the path to the file holding it; the `include` form is an error, since a setup has one system prompt. A file that cannot be read is found when the test runs, which reports `ERROR`. Optional: without it the harness keeps its own.
- `append_system_prompt` — text appended to the harness's own system prompt, which otherwise stays in place. Written as `override_system_prompt`, `include` form excluded.

  The two are exclusive: a test whose setup has both once its templates are merged is a load error. Neither is required.
- `skills` — skills added to the harness's own, one path or a list. Each path is a skill's directory, the one holding its `SKILL.md`, and resolves like any other path: `./` from the test file, absolute as is, anything else from the project root. It is taken literally, never globbed; a path that is not a directory, or a directory with no `SKILL.md` directly inside, is a load error. The skills are appended, never substituted: with `user_local`, the harness runs with every skill the user has plus these. A skill whose name one of the harness's own skills already has, or another in the list, is found only when the test runs: the test reports `ERROR`, naming the skill and both places it comes from. Optional: without it the harness has only its own. Appending is to the harness; between a template and a test the list is replaced like any other `setup` key, never joined (see [templates.md](templates.md)).
- `working_folder` — the initial contents of the workspace, not where the model works. The model works in the **workspace**, a folder skilleval clones from `working_folder` when the test starts, so the folder itself is never modified and every run starts from the same contents. A symbolic link in it is copied as a link, never followed. A path that is not a directory is a load error. Optional: without it the workspace starts empty.

  The workspace lives outside the project, in the system's temporary directory, under a folder skilleval creates and uses alone, with one folder per test; nothing to set up or configure. Being outside the project, the harness picks up none of the project's `CLAUDE.md` files, and no test file sits next to the model's work. The names are neutral, since the model can read its own working directory: neither the folder nor its parent says anything of skilleval or of the test. The same test always gets the same folder, and skilleval prints its path under a failure or an error, and with `-v` under every test that ran: a skipped one has touched no workspace.

  When a test starts, its workspace is emptied and filled again from `working_folder`. It is shared by the test's chained tasks and read by its `expect`, then left as it is once the test ends, whatever the outcome, for inspection until the test runs again. A workspace is the only folder skilleval ever empties.

```yaml
setup:
  harness: user_local
  permissions: bypass                  # never asks: edits files and runs commands freely
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

## Expect

Checks on the result of a task, run once the task is done and never shown to the model. `expect` is a list of blocks, as many as needed, each a mapping with one key naming what it checks, the way a workflow step is a `uses` or a `run`:

- `response` — the model's final message for the task: its last reply, not the whole conversation. Holds a list of constraint entries, written exactly as a static check's `constraints` ([static-checking.md](static-checking.md), Constraints) — same entries, parameters, shorthands and repetition — applied to that message as they would be to a prompt. Several `response` blocks read as one list.

  `response` reads only the text of the reply, never the workspace: a check naming a file or folder asserts that the reply mentions it, not that it exists or holds anything; that is what `file` is for.
- `file` — one file the task left in the workspace. Holds `with_path`, required, and beside it the checks, each constraint name as a key taking the same parameters as under `response`: `words`, `lines`, `contains*`, `matches*`, `paths`, `urls` and `code`. A key name appears once per block, so a second entry of the same name — a soft budget beside a hard one — goes in a second block for the same path.

  `with_path` is relative to the workspace the model worked in — never to `working_folder`, which only filled it at the start — and to nothing else: `./`, an absolute path and one climbing out with `..` are load errors, since nothing outside the workspace is in reach. It names one exact file, never a glob. The block asserts the file exists: a missing one fails with that finding and the block's checks are skipped, as does one that is not UTF-8 text. A block with `with_path` alone asserts existence and nothing more.

`severity` sets how a failure counts, `error` unless set to `warn`, at two levels. On a section it covers the whole of it, the existence of a `file` included; on one check it covers that check alone and wins over the section's. On a `file` block it sits beside `with_path`; on a `response` block beside `response`, since `response` holds a list. Where several blocks check the same thing, each one's `severity` covers its own checks, and the file has to exist at `error` unless every block naming it says `warn`:

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

The test reports `FAILED` for what the setup did or did not do: a failing check, a permission request, a limit reached. It reports `ERROR` for whatever kept it from running properly — the harness missing or crashing, a model it does not know, a credential it lacks, a skill-name clash — and stops there: no further task runs, nothing more is checked, and the reason is all it reports, without what earlier tasks found. Findings report under the case like a static check's, prefixed with `response` or the file's `with_path` and, when more than one task ran, the task's position in the chain: `task 2: response: words: ...`. What is not a check reports the same way, under the name of its key: `file` for a file that has to exist, `permissions`, `max_tokens`, `max_budget_usd`. The workspace follows as `workspace: <path>`. `expect` is optional: without it, a test passes when every task runs to its end within the limits.

## Later

Not specified yet; to come after everything above.

- MCP servers in `setup`, appended to the harness's own the way `skills` are.
- A finer handling of permissions than failing the test on the first request the harness cannot put to anyone.
- Scripts run in the workspace after a task, under `expect`, passing or failing by their exit code: a test suite checking the code the task wrote.
- Several tasks in one test, run in sequence with assertions between them. Like a template's task before the test's, they share the workspace and the conversation, so each task builds on the last: one task writes the tests, the next implements the code that passes them.

Worked example: [examples/evaluation.eval.yml](examples/evaluation.eval.yml) and the template it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
