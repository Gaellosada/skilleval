# Test file

A test file is YAML, named `*.eval.yml` or `*.eval.yaml` to be discovered. Its top-level keys are `root`, `judge_defaults`, `tests` and `templates`; it holds `tests`, `templates` or both, each as many times as needed.

Everything in the file is validated when it loads. An unknown key, a key repeated anywhere in the file but a top-level `tests` or `templates`, or a value of the wrong shape is a load error naming the file and what to fix, and the run exits with code 2. So is a file that cannot be read, is not UTF-8, is not valid YAML or is not a mapping. So is a value YAML cannot read, such as the date `2026-02-30`, until quoted.

## `root`

The project-root marker: the name of a file or a directory, such as `pyproject.toml` or `.git`. The project root is the nearest ancestor directory of the test file that holds it. A marker that no ancestor holds is a load error, and so is one that is not a single name, such as `../pyproject.toml`, an absolute path, `.` or `..`.

## `judge_defaults`

Which model answers the [`judge`](evaluations.md#judge) blocks of the file's evaluations, and what it may use: a mapping of `model`, `effort`, `harness`, `max_tokens` and `max_budget_usd`, written once. See [evaluations.md](evaluations.md#judge_defaults).

## Paths

A path written in a test file that starts with `./` is relative to the test file's directory. An absolute path is taken as is. Any other path, `../` ones included, is relative to the project root. In a file without `root`, any path not starting with `./` is a load error.

## `tests`

A mapping of test id to test. The id addresses the test in `needs`, on the command line and in reports. An id is a string: a key YAML reads as another type (`on`, `yes`, `1`, `null`) is a load error until quoted.

`tests` may appear more than once, before or after `templates`, which may too: the sections join in file order, and the tests run in that order. An id in two `tests` sections is a load error at `tests.<id>`. YAML 1.2 calls a repeated key invalid, and linters flag it, such as yamllint's `key-duplicates`; skilleval accepts it for `tests` and `templates` on purpose, so that a template can sit next to the tests that use it.

```yaml
# evals/skills.eval.yml
root: pyproject.toml
templates:
  house_style: {kind: static-check, lint: [chars]}
tests:
  skills: {kind: static-check, prompt: {include: .claude/skills/**/SKILL.md}, uses: ./skills.eval.yml#house_style}
templates:
  brief: {kind: static-check, constraints: [{words: {max: 300}}]}
tests:
  root-instructions: {kind: static-check, prompt: {file: CLAUDE.md}, uses: ./skills.eval.yml#brief}
```

Every test takes `kind`, `needs` and `uses`; the other keys depend on the kind. A `static-check` takes `prompt`, `lint`, `format` and `constraints`: its checks are its `lint`, `format` and `constraints` entries plus those of the templates it `uses`, described in [checks.md](checks.md). An `evaluation` takes `setup`, `model`, `task`, `expect`, `max_tokens` and `max_budget_usd`, described in [evaluations.md](evaluations.md). A key of the other kind is a load error.

## `templates`

A mapping of template name to reusable test body. See [templates.md](templates.md).

## `kind`

Required. What the test does, one of two; any other value is a load error.

- `static-check` reads the prompt as text and runs no model.
- `evaluation` runs a setup on its tasks and checks what they leave. See [evaluations.md](evaluations.md).

## `prompt`

Required in a `static-check`. The text the checks read, in one of three forms, and no other:

- a string: the prompt itself, written inline, as a YAML block scalar `|` for several lines. The test has one case. `markdown_links` and `paths_exist` need a file and are skipped for it; a skipped check does not fail the case.
- a mapping with `file`: one file, taken literally, never globbed. The test has one case.
- a mapping with `include`, and optionally `exclude`: every matched file. The test has one case per file.

Checks run against each case separately.

### `file`

One path, resolved as under [Paths](#paths).

### `include`

One glob, matched from the project root, or from the test file's directory when it starts with `./`. `**` crosses directories, dot-directories included. An `include` never matches a file inside a directory named `.skilleval`, wherever it is and even when the glob names it: that is where skilleval keeps the [results](evaluations.md#results) of evaluations. It reads as Python's `Path.glob`, where `**` stands only as a whole segment, and only files count. A pattern ending in `**` matches every file below, on every supported Python: `docs/**` reads as `docs/**/*`. An empty or absolute `include` is a load error.

An `include` left with no file, before or after `exclude`, is a misconfiguration, not an empty pass: the test has one case, reported as `ERROR`.

### `exclude`

One glob or a list. A file matched by `include` is dropped when its path, relative to where `include` is matched from, matches one of them. A leading `./` is dropped, as on `include`, so `{include: ./prompts/**/*.md, exclude: ./prompts/drafts/**}` reads both from the test file's directory. The syntax is under [Globs](#globs); a glob that does not compile is a load error.

## Globs

The syntax of `exclude` and of `except` on the `paths` constraint. A glob matches the whole path.

- `*`, `?` and `[...]` stop at a separator, `/` or `\`; `**` crosses separators, and `**/` also matches zero directories: `**/fixtures/**` matches `fixtures/a.md`.
- A class reads as in Python's `fnmatch`: `[!...]` negates, ranges stay, a leading `^`, a `]` first in the class and a backslash are literal, and an unclosed `[` is literal.
- A glob that does not compile, such as `[z-a]`, is a load error naming it.

## `needs`

One test id or a list, naming tests of the same file, of any kind, that must pass first. An unknown id, the test itself or a cycle is a load error.

A needed test counts as passed only when every one of its cases passed; warnings never block. Otherwise each case of the test that needs it is `SKIPPED` with the reason. So is it when the command line did not select every case of the needed test, as when [`--static-checks`](cli.md#--static-checks) leaves out the evaluation it needs.

Tests run in file order, except that a needed test is moved up to just before the first test that needs it.

## `uses`

Pulls templates into the test. See [templates.md](templates.md#uses).
