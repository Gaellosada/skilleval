# Templates

A template is a named, reusable test body pulled in with `uses`, the way a job calls a reusable workflow. It is meant for every kind — lint and constraints for a static-check, later a setup or grading scheme for an evaluation or benchmark.

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

A template adds to a test, never replaces anything in it. Pulling one in unions its checks with the test's own, and the test must satisfy every check from both sides.

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

A test that needs different rules uses a different template, or none. That keeps the merge rule to one sentence, at the cost of forking a template to relax it — revisit if that turns out to be common.
