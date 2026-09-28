# Templates

A template is a named, reusable test body pulled in with `uses`, the way a job calls a reusable workflow. It is meant for every kind — lint and constraints for a static-check, a setup, model, budgets, a task and its expectations for an evaluation.

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

A template names no target and no identity — `prompt`, `name`, `needs` and `uses` are errors in one — and its `kind` must match the test using it. A path inside one, such as a word list, resolves against the template's own file and its own `root`. `uses` takes one reference or a list, each `path#template`. A file can both define templates and run tests.

## Merging

A template adds to a test: what only one side sets is kept. **Where both set the same thing, the test always overrides the template** — the one rule every kind and key follows. With several templates in `uses`, they apply in list order and the test's own keys last.

### Static checks

Checks accumulate: pulling a template in adds its lint and constraints to the test's own. Where both sides set the same thing, the test's own wins.

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
    prompt:
      file: SKILL.md
    uses: ./shared.eval.yml#house_style
    lint:
      - paths_exist:
          severity: warn
    constraints:
      - words:
          max: 600
```

**A lint rule named on both sides takes the test's severity.** `paths_exist` is inherited at `error` and declared locally at `warn`, so it runs at `warn`; a bare name in the test is `error`, as anywhere else.

**`words`, `lines`, `paths`, `urls` and `code` override parameter by parameter.** Both sides set `max` on `words`, so the test's 600 replaces the template's 400. A parameter only one side sets is kept: had the test written `words: {min: 50}`, the merged check would be `min: 50, max: 400`. A parameter is one key of the entry: `count` on `paths`, `urls` and `code` is replaced whole, `min` and `max` of `words` and `lines` one by one. When the template has several entries of that name, the test's parameters override each of them, and when the test has several, each overrides in turn, so one entry remains; `severity` counts only where the test writes it.

**`contains`, `contains_any`, `contains_none`, `matches`, `matches_any` and `matches_none` are additive.** Two entries with different words or patterns are two requirements, not one set twice, so the template's and the test's all stand.

**The nearest format wins.** A test's own `format` replaces its templates' one, severity included; between templates, the later in `uses` replaces the earlier. A template's format holds only while nothing nearer names one.

### Evaluations

`setup`, `model`, `max_tokens` and `max_budget_usd` do not accumulate: a test has one of each, so the test's own value overrides the template's, key by key, and within `setup` sub-key by sub-key. A list is a single value too: a test's `skills` replaces its template's list whole, never joined with it, so a test wanting the template's skills and one more lists them all. Required keys such as `harness`, and exclusive ones such as `override_system_prompt` and `append_system_prompt`, are checked after merging: a template can supply a required key, and a template's system prompt key clashes with a test's other one. The keys themselves are in [evaluations.md](evaluations.md).

**Tasks chain.** A template's `task` and the test's are two tasks, not one set twice, so both run: the templates' first, in `uses` order, then the test's, one after the other in the same workspace and conversation. A template can so set up the ground — write the tests, seed a file — for the task the test brings.

**Expectations follow their task.** A template's `expect` is checked on that template's own task; one with no task beside it, in a template holding none or in a test whose only task comes from templates, applies to the nearest task above it in the chain ([evaluations.md](evaluations.md), Expect). Where several `expect` lists land on the same task, their blocks join: the checks of every `response` block form one list, and so do those of every `file` block for the same `with_path`, a path only one side names kept. Each list merges exactly as a static check's `constraints` above: `words`, `lines`, `paths`, `urls` and `code` override parameter by parameter, the nearer side winning, and `contains*` and `matches*` stand side by side. A file's existence is the exception to the test overriding: it is a warning only when every block naming the file says `warn`, the template's and the test's alike.

```yaml
# shared.eval.yml
templates:
  reference:
    kind: evaluation
    setup:
      harness: user_local
      override_system_prompt:
        file: ./prompts/reviewer.md
    model: claude-opus-5-5
    max_tokens: 200000
```

```yaml
tests:
  refactor-skill:
    kind: evaluation
    uses: ./shared.eval.yml#reference
    task: Split utils.py into one module per concern.
    model: claude-sonnet-5       # overrides the template's model
```

The test runs with the template's harness and system prompt, `claude-sonnet-5` and a budget of 200000 tokens.
