# Evaluations

An evaluation runs a setup against a model and grades the result. It is a `kind: evaluation` test, declared under `tests` like any other and addressed by the same node ids; the test file itself is described in [README.md](README.md).

```yaml
tests:
  refactor-skill:
    kind: evaluation
    setup: ...                   # specified later
    model: claude-opus-5-5
    max_tokens: 200000
```

- `setup` — what the model runs in. Specified later.
- `model` — the model to run, exactly one.
- `max_tokens` — the most tokens the whole test may use, a positive integer. Going beyond it fails the test.

`prompt`, `lint`, `format` and `constraints` belong to static checks and are errors in an evaluation. `needs` and `uses` work as for any test; how a template's keys combine with the test's is in [templates.md](templates.md).
