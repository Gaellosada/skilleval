# Templates

A template is a named set of checks that tests pull in with `uses`.

## `templates`

A top-level mapping of template name to template. A name is a string, like a test id. A file may define templates and tests; a file with only templates contributes no tests.

A template takes `kind` (required), `lint`, `format` and `constraints`, written as in a test. Any other key is a load error: a template has no `prompt`, no `needs` and no `uses`.

A path inside a template, such as a word list, resolves against the template's own file and its own `root`.

## `uses`

A key of a test. One reference or a list, each `path#name`: `path` is the file that defines the template, resolved like any path in the test file, and `name` is the template. A reference without `#name`, a `path` that is not a file, or a `name` the file does not define is a load error.

## Merging

A template adds checks to a test and never replaces any. The test runs every check from its templates and its own, and must satisfy all of them.

- A lint rule or format named both in a template and in the test runs once, at the stricter severity: `error` over `warn`. A test cannot downgrade a template's check.
- Constraints all stand. Two bounds on the same measure both apply, so the stricter one binds; a template can be tightened by adding a check, never loosened.
