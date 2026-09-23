# skilleval — main spec

The entry point. Sub-specs: [cli.md](cli.md), [static-checking.md](static-checking.md).

## Goal

Declarative, file-based workflows — shaped like GitHub Actions, but executed by `skilleval` itself — that test a given **setup** (harness + model + skills + config), or a single **component** of it such as one skill. The unit under test is the setup or the component, not the model.

## Documentation

Everything lives in `docs/`: every keyword, its parameters, what it does, an example of its usage. Written for humans and agents alike — an undocumented keyword is unfinished, and the docs, not the source, are what an agent is pointed at.

## Interfaces

An importable Python package with a CLI over the same API. Specified in [cli.md](cli.md), which also covers discovery, node ids and exit codes.

## Test file

A file declares tests, keyed by id. The id is what `needs` and the command line address; the optional `name` is the label in reports. `kind` says what the test does and decides which other keys are valid:

- `static-check` — reads a `prompt` as text, runs no model. Deterministic and free. See [static-checking.md](static-checking.md).
- `evaluation` — runs one `setup` against tasks and grades the answers. Passes or fails like any test.
- `benchmark` — runs a matrix of setups over the same tasks and reports comparative numbers. Fails only against an explicit threshold or baseline: its job is measurement, not a verdict.

```yaml
name: Skill house style          # optional, defaults to the file name
skilleval_version: ">=0.4"       # optional, the tool version these tests expect
root: pyproject.toml             # the project-root marker; without it, only ./ paths are allowed

tests:

  house-style:
    kind: static-check
    name: Skill house style      # optional, shown in reports
    prompt:
      include: .claude/skills/**/SKILL.md
      exclude: "**/fixtures/**"
    format: anthropic-skill
    lint: [chars, markdown_links]
    constraints:
      - words:
          max: 400

  exercises:
    kind: evaluation
    name: Refactor exercises
    needs: house-style           # skipped unless that test passed
    setup:
      harness: claude-code
      model: claude-opus-5
      skills: .claude/skills/refactor
      instructions: CLAUDE.md
    tasks: ./tasks/refactor/*.yml
```

`prompt` has two forms and no others: a single path, taken literally and never globbed, or a mapping with `include`, one glob, and an optional `exclude` of one glob or a list. Checks run against each matched file separately. `setup` names the pieces assembled into the thing being run, and the tasks run against that whole setup.

`needs` names tests that must pass first; a test whose dependency failed reports as skipped, not run. Gating an evaluation on a static-check is the case worth having — no point spending tokens on a skill whose text is already broken. Warnings never block, since they never fail.

A path prefixed with `./` is relative to the test file; any other is relative to the project root, the nearest ancestor of the test file holding the marker named by `root`. A file omitting `root` may use only `./` paths: a root-relative path is then an error, as is a marker that is never found.

A check entry is a bare name when it takes no parameters, the name plus parameters otherwise. Any entry accepts `severity`, always `error` unless set to `warn`; a `warn` entry reports but never fails, so a check that is 90% right can be watched instead of deleted, and `severity: error` makes an inherited warning fail again. A check may appear more than once — a soft budget beside a hard one — each entry standing alone, with an optional `id` so a template override can target one of them.

Checks within a test are unordered and all report; when a prompt cannot be read or parsed, its remaining checks are skipped rather than failing one by one.

## Node ids

A test produces one case per thing it fans out over, and a node id addresses them: the file, the test id, then the fan-out key in brackets.

```
evals/skills.eval.yml::house-style
evals/skills.eval.yml::house-style[.claude/skills/refactor/SKILL.md]
```

- A test with no fan-out and no file behind it has one nameless case, addressed by its id alone. Brackets are an error.
- A test whose prompt is a single file has one case and accepts either form: the id alone, or the id with that file in brackets.
- A test that fans out has one case per match. The id alone selects all of them; brackets are required to select one.

## Reuse

A template is a named, reusable test body pulled in with `uses`, the way a job calls a reusable workflow. It works for every kind: lint and constraints for a static-check, a setup or grading scheme for an evaluation or benchmark.

```yaml
# evals/shared.eval.yml
templates:

  house_style:                   # static-check rules
    kind: static-check
    lint: [chars, markdown_links]
    constraints:
      - words:
          max: 400

  reference_setup:               # the setup an evaluation runs against
    kind: evaluation
    setup:
      harness: claude-code
      model: claude-opus-5
```

```yaml
tests:
  house-style:
    kind: static-check
    prompt:
      include: .claude/skills/**/SKILL.md
    uses: ./shared.eval.yml#house_style

  exercises:
    kind: evaluation
    uses: ./shared.eval.yml#reference_setup
    tasks: ./tasks/refactor/*.yml
```

A template names no target — the test supplies its own `prompt` or `tasks` — and its `kind` must match the test using it. `uses` takes one reference or a list, each `path#template`; the test's own keys apply last, with named-check lists unioning and everything else merging by key. A file can both define templates and run tests.

## Static checks

Checks on a prompt that run without invoking a model — deterministic, no harness, no cost. Specified in [static-checking.md](static-checking.md).
