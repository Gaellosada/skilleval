# Templates

A template is a named set of checks that tests pull in with `uses`.

## `templates`

A top-level mapping of template name to template. A name is a string, like a test id. A file may define templates and tests; a file with only templates contributes no tests.

A template takes `kind` (required, and the kind of every test that uses it), `lint`, `format` and `constraints`, written as in a test. Any other key is a load error: a template has no `prompt`, no `needs` and no `uses`.

A path inside a template, such as a word list, resolves against the template's own file and its own `root`.

## `uses`

A key of a test. One reference or a list, each `path#name`: `path` is the file that defines the template, resolved like any path in the test file, and `name` is the template. A reference without `#name`, a `path` that is not a file, a `name` the file does not define, or a template of another kind than the test is a load error.

## Merging

A template adds checks to a test. The test runs every check from its templates and its own, but an overridden `format`, and must satisfy all of them.

- A lint rule named both in a template and in the test runs once, at the stricter severity: `error` over `warn`. A test cannot downgrade a template's lint.
- The nearest `format` wins: the test's own replaces its templates' one, severity included, and a later template in `uses` replaces an earlier one.
- Constraints all stand. Two bounds on the same measure both apply, so the stricter one binds; a template can be tightened by adding a check, never loosened.
