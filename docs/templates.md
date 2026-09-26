# Templates

A template is a named set of checks that tests pull in with `uses`.

## `templates`

A top-level mapping of template name to template. A name is a string, like a test id. A file may define templates and tests; a file with only templates contributes no tests.

A template takes `kind` (required, and the kind of every test that uses it), `lint`, `format` and `constraints`, written as in a test. Any other key is a load error: a template has no `prompt`, no `needs` and no `uses`.

A path inside a template, such as a word list, resolves against the template's own file and its own `root`.

## `uses`

A key of a test. One reference or a list, each `path#name`: `path` is the file that defines the template, resolved like any path in the test file, and `name` is the template. A reference without `#name`, a `path` that is not a file, a `name` the file does not define, or a template of another kind than the test is a load error.

## Merging

A template adds checks to a test: what only one side sets is kept, and where both set the same thing the test's own wins. Several templates in `uses` apply in list order, the test's own keys last.

- `contains`, `contains_any`, `contains_none`, `matches`, `matches_any` and `matches_none` are additive: two entries are two requirements, so the template's and the test's all stand.
- A lint rule, or a `words`, `lines`, `paths`, `urls` or `code` constraint, named on both sides is the template's entry with the test's parameters written over it, one by one: `words: {max: 600}` over a template's `words: {min: 50, max: 400}` gives `min: 50, max: 600`. A lint takes the test's severity, a bare name being `error`; a constraint takes it where the test writes one, else the template's. When the template has several entries of that name, the test's parameters override each of them.
- The nearest `format` wins: the test's own replaces its templates' one, severity included, and a later template in `uses` replaces an earlier one.
