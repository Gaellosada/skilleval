# Evaluations

An evaluation runs a setup against a model and grades the result. It is a `kind: evaluation` test, declared under `tests` like any other and addressed by the same node ids; the test file itself is described in [README.md](README.md).

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
    max_tokens: 200000
    max_budget_usd: 5
```

- `setup` — what the model runs in, described below.
- `model` — the model to run, exactly one.
- `max_tokens` — the most tokens the whole test may use, a positive integer.
- `max_budget_usd` — the most the whole test may spend, in US dollars, a positive number.

`max_tokens` and `max_budget_usd` are independent and both optional: either, both or neither may be set, and with neither the test runs unlimited. Whichever limit is hit first stops the test, which then fails.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors in an evaluation. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).

## Setup

- `harness` — what runs the model. Required: a test whose setup has none once its templates are merged is a load error, as is any value other than these two:
    - `none` — no harness; the model is called directly.
    - `user_local` — the harness installed on the machine running skilleval, run unattended: it receives each task, works until it answers, and never waits for a person. It runs as the user has it configured — their settings, skills and servers apply as when they start it themselves — with the copy of `working_folder` as its working directory, so any configuration that folder holds applies too. The test's `model` and `override_system_prompt` take precedence over that configuration.

  `none` is not supported yet: for now, a test using it is a load error saying so.
- `override_system_prompt` — a system prompt replacing the harness's own. Written as for a static check's `prompt`: a string, the system prompt itself inline, or a mapping with `file`, the path to the file holding it; the `include` form is an error, since a setup has one system prompt. Optional: without it the harness keeps its own.
- `working_folder` — a directory whose files the model can use: it runs in a copy of it, so the folder itself is never modified and every run starts from the same contents. A path that is not a directory is a load error. Optional: without it the model runs in an empty folder.

```yaml
setup:
  harness: user_local
  override_system_prompt:
    file: prompts/reviewer.md
  working_folder: ./fixtures/refactor
```

```yaml
setup:
  harness: user_local
  override_system_prompt: You review Python pull requests.
```

Worked example: [examples/evaluation.eval.yml](examples/evaluation.eval.yml) and the template it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
