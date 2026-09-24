# Templates

A template is a named, reusable test body pulled in with `uses`, the way a job calls a reusable workflow. It is meant for every kind — lint and constraints for a static-check, a setup, model and token budget for an evaluation.

```yaml
# evals/shared.eval.yml
templates:

  house_style:
    kind: static-check
    lint: [chars, markdown_links]
    constraints:
      - words:
          max: 400
```

```yaml
tests:
  house-style:
    kind: static-check
    prompt:
      include: .claude/skills/**/SKILL.md
    uses: ./shared.eval.yml#house_style
```

A template names no target and no identity — `prompt`, `tasks`, `name`, `needs` and `uses` are errors in one — and its `kind` must match the test using it. A path inside one, such as a word list, resolves against the template's own file and its own `root`. `uses` takes one reference or a list, each `path#template`. A file can both define templates and run tests.

## Merging

A template adds to a test: whatever can accumulate does, and the test must satisfy everything from both sides. Where the two sides cannot both hold, the test's own value overrides the template's. With several templates in `uses`, they apply in list order and the test's own keys last.

### Static checks

Checks accumulate. Pulling a template in unions its lint and constraints with the test's own.

```yaml
# shared.eval.yml
templates:
  house_style:
    kind: static-check
    lint: [chars, markdown_links, paths_exist]
    constraints:
      - words:
          max: 400
```

```yaml
tests:
  skills:
    kind: static-check
    prompt: SKILL.md
    uses: ./shared.eval.yml#house_style
    lint:
      - paths_exist:
          severity: warn
    constraints:
      - words:
          max: 600
```

**A lint rule named on both sides keeps the stricter severity.** `paths_exist` is inherited at `error` and declared locally at `warn`, so it runs at `error`. A template's gate cannot be downgraded by the test using it.

**Constraints both stand.** The merged test carries `words: max 400` from the template and `words: max 600` of its own, so 400 is what binds. Tightening a template works by adding a stricter check; loosening one does not work at all.

**`format` is overridden.** A test has one format, so the test's own replaces the template's, parameters and severity included.

A test that needs looser checks uses a different template, or none, at the cost of forking a template to relax it — revisit if that turns out to be common.

### Evaluations

`setup`, `model` and `max_tokens` do not accumulate: a test has one of each, so the test's own value overrides the template's, key by key. The keys themselves are in [evaluations.md](evaluations.md).

```yaml
# shared.eval.yml
templates:
  reference:
    kind: evaluation
    setup: ...
    model: claude-opus-5-5
    max_tokens: 200000
```

```yaml
tests:
  refactor-skill:
    kind: evaluation
    uses: ./shared.eval.yml#reference
    model: claude-sonnet-5       # overrides the template's model
```

The test runs the template's `setup` with `claude-sonnet-5` and a budget of 200000 tokens.
