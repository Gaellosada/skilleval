# Evaluations

An evaluation runs a setup against a model and grades the result. It is a `kind: evaluation` test, declared under `tests` like any other and addressed by the same node ids; the test file itself is described in [README.md](README.md).

> **Important — the model never knows it is being evaluated.** It sees the task, as a user would give it, and nothing of the evaluation around it: no test id, no grading criteria, no expected answer, no mention of skilleval, in its prompt, its working folder or anything else it can read. A model that knows it is tested behaves differently, and the result would measure that instead of the setup.

```yaml
tests:
  refactor-skill:
    kind: evaluation
    setup:
      harness: user_local
      override_system_prompt:
        file: prompts/reviewer.md
      working_folder: ./fixtures/refactor
    model: claude-opus-5-5
    task: Split utils.py into one module per concern.
    max_tokens: 200000
    max_budget_usd: 5
```

- `task` — what the model is asked, a string given to it as written, as a user would type it. Inline only: no `file` or `include` form. A template may hold one too: its task runs before the test's, in the same workspace and conversation (see [templates.md](templates.md)). Required once templates are merged: a test with no task of its own or from a template is a load error.
- `setup` — what the model runs in, described below.
- `model` — the model to run, exactly one.
- `max_tokens` — the most tokens the whole test may use, a positive integer.
- `max_budget_usd` — the most the whole test may spend, in US dollars, a positive number.

`max_tokens` and `max_budget_usd` are independent and both optional: either, both or neither may be set, and with neither the test runs unlimited. Whichever limit is hit first stops the test, which then fails.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors in an evaluation. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).

## Setup

- `harness` — what runs the model. Required: a test whose setup has none once its templates are merged is a load error, as is any value other than these two:
    - `none` — no harness; the model is called directly.
    - `user_local` — the harness installed on the machine running skilleval, run unattended: it receives each task, works until it answers, and never waits for a person. It runs as the user has it configured — their settings, skills and servers apply as when they start it themselves — with the copy of `working_folder` as its working directory, so any configuration that folder holds applies too. The test's `model` and system prompt keys take precedence over that configuration.

  `none` is not supported yet: for now, a test using it is a load error saying so.
- `override_system_prompt` — a system prompt replacing the harness's own. Written as for a static check's `prompt`: a string, the system prompt itself inline, or a mapping with `file`, the path to the file holding it; the `include` form is an error, since a setup has one system prompt. Optional: without it the harness keeps its own.
- `append_system_prompt` — text appended to the harness's own system prompt, which otherwise stays in place. Written as `override_system_prompt`, `include` form excluded.

  The two are exclusive: a test whose setup has both once its templates are merged is a load error. Neither is required.
- `skills` — skills added to the harness's own, one path or a list. Each path is a skill's directory, the one holding its `SKILL.md`, and resolves like any other path: `./` from the test file, absolute as is, anything else from the project root. It is taken literally, never globbed; a path that is not a directory, or a directory with no `SKILL.md` directly inside, is a load error. The skills are appended, never substituted: with `user_local`, the harness runs with every skill the user has plus these. A skill whose name one of the harness's own skills already has, or another in the list, is found only when the test runs: the test reports `ERROR`, naming the skill and both places it comes from. Optional: without it the harness has only its own. Appending is to the harness; between a template and a test the list is replaced like any other `setup` key, never joined (see [templates.md](templates.md)).
- `working_folder` — a directory whose files the model can use: it runs in a copy of it, so the folder itself is never modified and every run starts from the same contents. A path that is not a directory is a load error. Optional: without it the model runs in an empty folder.

```yaml
setup:
  harness: user_local
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

## Later

Not specified yet; to come after everything above.

- MCP servers in `setup`, appended to the harness's own the way `skills` are.
- Several tasks in one test, run in sequence with assertions between them. Like a template's task before the test's, they share the workspace and the conversation, so each task builds on the last: one task writes the tests, the next implements the code that passes them.

Worked example: [examples/evaluation.eval.yml](examples/evaluation.eval.yml) and the template it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
