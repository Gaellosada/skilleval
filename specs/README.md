# skilleval — main spec

The entry point. Sub-specs: [static-checking.md](static-checking.md).

## Goal

Declarative, file-based workflows — shaped like GitHub Actions, but executed by `skilleval` itself — that test a given **setup** (harness + model + skills + config), or a single **component** of it such as one skill. The unit under test is the setup or the component, not the model.

## Documentation

Everything lives in `docs/`: every keyword, its parameters, what it does, an example of its usage. Written for humans and agents alike — an undocumented keyword is unfinished, and the docs, not the source, are what an agent is pointed at.

## Interfaces

Importable Python package, with a CLI as a thin wrapper over the same API. The CLI mirrors pytest: same argument forms, node ids, selection flags and exit codes.

```
skilleval evals/skills/                   # an example path
```

## Test file

A file declares tests, keyed by id. An id is addressed by `needs` and on the command line; the optional `name` inside a test is its label in reports. `kind` says what the test does, and decides which other keys are valid:

- `static-check` — reads a `prompt` as text, runs no model. Deterministic and free. See [static-checking.md](static-checking.md).
- `evaluation` — runs one `setup` against tasks and grades the answers. Pass or fail, like any other test.
- `benchmark` — runs a matrix of setups against the same tasks and reports comparative numbers. It fails only against an explicit threshold or baseline, since its job is measurement, not a verdict.

```yaml
name: Skill house style          # optional, defaults to the file name
skilleval_version: ">=0.4"       # optional, the tool version these tests expect

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

`prompt` has two forms and no others: a single path, taken literally and never globbed, or a mapping with `include`, one glob, and an optional `exclude` of one glob or a list of them. The checks run against each matched file separately. `setup` names the pieces assembled into the thing being run, and the tasks run against that whole setup.

`needs` names tests that must pass first; a test whose dependency failed reports as skipped, not run. Gating an evaluation on a static-check is the case worth having — no point spending tokens on a skill whose text is already broken. Warnings never block, since they never fail.

Paths resolve from the project root — the nearest ancestor holding `pyproject.toml`, `.git` or a skilleval config — unless prefixed with `./`, which is relative to the test file. Each case is a node id in the CLI's pytest shape, the test id plus what it fanned out over: `evals/skills.yml::house-style[.claude/skills/refactor/SKILL.md]`.

A check entry is a bare name when it takes no parameters, the name plus parameters otherwise. Any entry accepts `severity`, always `error` unless set to `warn`; a `warn` entry reports but never fails, so a check that is 90% right can be watched instead of deleted, and `severity: error` is how a test makes an inherited warning fail again. A check may appear more than once — a soft budget beside a hard one — each entry standing alone, with an optional `id` so a template override can target one of them.

Checks within a test are unordered and all report; when a prompt cannot be read or parsed, its remaining checks are skipped rather than failing one by one.

## Reuse

A template is a named, reusable test body pulled in with `uses`, the way a job calls a reusable workflow. It works for every kind: lint and constraints for a static-check, a setup or a grading scheme for an evaluation or benchmark. Any file name, anywhere; nothing is discovered by convention.

```yaml
# evals/shared.yml
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
    uses: ./shared.yml#house_style

  exercises:
    kind: evaluation
    uses: ./shared.yml#reference_setup
    tasks: ./tasks/refactor/*.yml
```

A template names no target — the test supplies its own `prompt` or `tasks` as usual — and its `kind` must match the test that uses it. `uses` takes one reference or a list, each `path#template`; the test's own keys apply last, with named-check lists unioning and everything else merging by key. A file can both define templates and run tests.

## Static checks

Checks on a prompt that run without invoking a model — deterministic, no harness, no cost. Specified in [static-checking.md](static-checking.md).
