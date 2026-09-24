# Test file

A test file is YAML, named `*.eval.yml` or `*.eval.yaml` to be discovered. Its top-level keys are `root`, `tests` and `templates`; it holds `tests`, `templates` or both.

Everything in the file is validated when it loads. An unknown key, a key repeated anywhere in the file, or a value of the wrong shape is a load error naming the file and what to fix, and the run exits with code 2.

## `root`

The project-root marker: the name of a file or a directory, such as `pyproject.toml` or `.git`. The project root is the nearest ancestor directory of the test file that holds it. A marker that no ancestor holds is a load error.

## Paths

A path written in a test file that starts with `./` is relative to the test file's directory. Any other relative path, `../` ones included, is relative to the project root, and is a load error in a file without `root`.

## `tests`

A mapping of test id to test. The id addresses the test in `needs`, on the command line and in reports. An id is a string: a key YAML reads as another type (`on`, `yes`, `1`, `null`) is a load error until quoted.

A test takes `kind`, `prompt`, `needs`, `uses`, `lint`, `format` and `constraints`. Its checks are its `lint`, `format` and `constraints` entries plus those of the templates it `uses`; they are described in [checks.md](checks.md).

## `templates`

A mapping of template name to reusable checks. See [templates.md](templates.md).

## `kind`

Required. What the test does. The only kind is `static-check`: it reads the prompt as text and runs no model. Any other value is a load error.

## `prompt`

Required. The text the checks read, in one of three forms, and no other:

- a path: one file, taken literally, never globbed. The test has one case.
- a mapping with `text`: the prompt written inline. The test has one case.
- a mapping with `include`, and optionally `exclude`: every matched file. The test has one case per file.

Checks run against each case separately.

### `text`

The prompt, inline. `markdown_links` and `paths_exist` need a file and are skipped for it; a skipped check does not fail the case.

### `include`

One glob, matched from the project root, or from the test file's directory when it starts with `./`. `**` crosses directories, dot-directories included. An empty or absolute `include` is a load error.

An `include` left with no file, before or after `exclude`, is a misconfiguration, not an empty pass: the test has one case, reported as `ERROR`.

### `exclude`

One glob or a list. A file matched by `include` is dropped when its path, relative to where `include` is matched from, matches one of them. The syntax is under [Globs](#globs); a glob that does not compile is a load error.

## Globs

The syntax of `exclude` and of `except` on the `paths` constraint. A glob matches the whole path.

- `*`, `?` and `[...]` stop at a separator; `**` crosses separators.
- A class reads as in Python's `fnmatch`: `[!...]` negates, ranges stay, a leading `^` and a backslash are literal, and an unclosed `[` is literal.
- A glob that does not compile, such as `[z-a]`, is a load error naming it.

## `needs`

One test id or a list, naming tests of the same file that must pass first. An unknown id, the test itself or a cycle is a load error.

A needed test counts as passed only when every one of its cases passed; warnings never block. Otherwise each case of the test that needs it is `SKIPPED` with the reason. So is it when the command line did not select every case of the needed test.

Tests run in file order, except that a needed test is moved up to just before the first test that needs it.

## `uses`

Pulls templates into the test. See [templates.md](templates.md#uses).
