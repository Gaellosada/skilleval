# skilleval — main spec

The entry point. Sub-specs: [cli.md](cli.md), [templates.md](templates.md), [static-checking.md](static-checking.md), [evaluations.md](evaluations.md), [config.md](config.md) and [benchmarks.md](benchmarks.md), the last still to be written.

## Goal

Declarative, file-based workflows — shaped like GitHub Actions, but executed by `skilleval` itself — that test a given **setup** (harness + model + skills + config), or a single **component** of it such as one skill. The unit under test is the setup or the component, not the model.

## Documentation

Everything lives in `docs/`: every keyword, its parameters, what it does, an example of its usage. Written for humans and agents alike — an undocumented keyword is unfinished, and the docs, not the source, are what an agent is pointed at.

## Interfaces

An importable Python package with a CLI over the same API. Specified in [cli.md](cli.md), which also covers discovery, node ids and exit codes.

## Platforms

Linux, WSL included. Windows outside WSL is not supported, and macOS is untested; what stands in the way is listed in `docs/limits.md`, with the other limits a user has to know.

## Test file

A file declares tests, keyed by id. `tests` and `templates` may each appear at the top level as many times as needed, interleaved in any order: their entries join in file order, and an id in two `tests` sections, or a name in two `templates` sections, is a load error at `tests.<id>` or `templates.<name>`, as a repeated key is anywhere else. Beside them, each written once, `root` names the project root and `judge_defaults` sets the judge of the file's `judge` blocks ([evaluations.md](evaluations.md), The judge). An id, like a template name, is a string: a key YAML reads as another type (`on`, `yes`, `1`, `null`) is a load error until quoted. The id is what `needs`, the command line and reports address. `kind` says what the test does and decides which other keys are valid:

- `static-check` — reads a `prompt` as text, runs no model. Deterministic and free. See [static-checking.md](static-checking.md).
- `evaluation` — runs one `setup` on its tasks and checks the results, the replies and the files left behind. Passes or fails like any test. See [evaluations.md](evaluations.md).
- `benchmark` — runs a matrix of setups over the same tasks and reports comparative numbers. Fails only against an explicit threshold or baseline: its job is measurement, not a verdict. Not specified yet: until it is, the kind is a load error.

```yaml
root: pyproject.toml             # the project-root marker; without it, only ./ paths are allowed

tests:

  house-style:
    kind: static-check
    prompt:
      include: .claude/skills/**/SKILL.md
      exclude: "**/fixtures/**"
    format: anthropic-skill
    lint: [chars, markdown_links]
    constraints:
      - words:
          max: 400

  root-instructions:
    kind: static-check
    needs: house-style           # skipped unless that test passed
    prompt:
      file: CLAUDE.md
    format: anthropic-claude
```

`prompt` has three forms and no others: a string, the prompt itself written inline (a YAML block scalar `|` for several lines); a mapping with `file`, a single path, taken literally and never globbed; or a mapping with `include`, one glob where `**` crosses directories, dot-directories included, and a trailing `**` matches every file below on every supported Python, which never matches a file inside a directory named `.skilleval`, skilleval's own, where evaluations keep their results ([evaluations.md](evaluations.md)), even when the glob names it, and an optional `exclude` of one glob or a list, matched against each path relative to the project root, or to the test file's directory for a `./` include, a leading `./` on it dropped as on the include; an empty or absolute `include` is a load error, and so is an `exclude` glob that does not compile (the glob syntax is in [static-checking.md](static-checking.md), under Paths). Checks run against each matched file separately. An `include` matching nothing, before or after `exclude`, is a misconfiguration, not an empty pass: the test reports `ERROR` under the bare node id `file::id`.

`needs` names tests that must pass first — one id or a list, within the same file; an unknown id or a cycle is a load error. A needed test counts as passed only when every one of its fanned-out cases passed, and cases held back this way report `SKIPPED` with the reason; so does a test whose dependency the command line did not select. Tests run in file order, except that a needed test is pulled up to just before the first test that needs it. Gating an evaluation on a static-check is the case worth having — no point spending tokens on a skill whose text is already broken. Warnings never block, since they never fail.

A path prefixed with `./` is relative to the test file; an absolute one is taken as is; any other is relative to the project root, the nearest ancestor of the test file holding the marker named by `root`, a file or a directory such as `.git`. A file omitting `root` may use only `./` paths: a root-relative or absolute path is then an error, as is a marker that is never found.

A check entry is a bare name when it takes no parameters, the name plus parameters otherwise; a name with nothing after its colon (`- paths:`) is a load error, not a check without parameters. Any entry accepts `severity`, always `error` unless set to `warn`; a `warn` entry reports but never fails, so a check that is 90% right can be watched instead of deleted, and `severity: error` makes an inherited warning fail again. A constraint may appear more than once — a soft budget beside a hard one — each entry standing alone; a lint is identified by its name, and naming one twice in a test is an error; a static check has one `format`.

Checks within a test are unordered and all report; when a prompt cannot be read, or opens a `---` frontmatter block on line 1 that never closes, its remaining checks are skipped rather than failing one by one. A check skipped because the prompt is inline text does not fail its case.

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

A template is a named, reusable test body pulled into a test with `uses`, adding its checks to the test's own. Specified in [templates.md](templates.md).

## Static checks

Checks on a prompt that run without invoking a model — deterministic, no harness, no cost. Specified in [static-checking.md](static-checking.md).
