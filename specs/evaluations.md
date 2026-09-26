# Evaluations

An evaluation runs a setup against a model and grades the result. It is a `kind: evaluation` test, declared under `tests` like any other and addressed by the same node ids; the test file itself is described in [README.md](README.md).

```yaml
tests:
  refactor-skill:
    kind: evaluation
    setup:
      system_prompt:
        file: prompts/reviewer.md
      working_folder: ./fixtures/refactor
    model: claude-opus-5-5
    max_tokens: 200000
```

- `setup` — what the model runs in, described below.
- `model` — the model to run, exactly one.
- `max_tokens` — the most tokens the whole test may use, a positive integer. Going beyond it fails the test.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors in an evaluation. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).

## Setup

- `system_prompt` — the system prompt, replacing the harness's own, the way a main `CLAUDE.md` would. Written as for a static check's `prompt`: a string, the system prompt itself inline, or a mapping with `file`, the path to the file holding it; the `include` form is an error, since a setup has one system prompt. Optional: without it the model runs with no system prompt, as with an empty `CLAUDE.md`.
- `working_folder` — a directory whose files the model can use: it runs in a copy of it, so the folder itself is never modified and every run starts from the same contents. A path that is not a directory is a load error. Optional: without it the model runs in an empty folder.

```yaml
setup:
  system_prompt:
    file: prompts/reviewer.md
  working_folder: ./fixtures/refactor
```

```yaml
setup:
  system_prompt: You review Python pull requests.
```

Worked example: [examples/evaluation.eval.yml](examples/evaluation.eval.yml) and the template it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
