# Templates

A template is a named, reusable test body that tests pull in with `uses`: the checks of a `static-check`, or the setup, model, limits, task and expectations of an `evaluation`.

## `templates`

A top-level mapping of template name to template. A name is a string, like a test id. A file may define templates and tests; a file with only templates contributes no tests. Like `tests`, `templates` may appear more than once, the sections joining ([test-file.md](test-file.md#tests)); a name in two of them is a load error at `templates.<name>`.

A template takes `kind` (required, and the kind of every test that uses it) and the keys of a test of that kind, written as in a test: `lint`, `format` and `constraints`, or `setup`, `model`, `task`, `expect`, `max_tokens` and `max_budget_usd`. Any other key is a load error: a template has no `prompt`, no `needs` and no `uses`.

A path inside a template, such as a word list, resolves against the template's own file and its own `root`.

## `uses`

A key of a test. One reference or a list, each `path#name`: `path` is the file that defines the template, resolved like any path in the test file, and `name` is the template. A reference without `#name`, a `path` that is not a file, a `name` the file does not define, or a template of another kind than the test is a load error. The file can have any name: only its `root` and `templates` are read.

## Merging

A template adds to a test: what only one side sets is kept, and where both set the same thing the test's own wins. Several templates in `uses` apply in list order, the test's own keys last. The checks of a `static-check` merge as follows; an evaluation merges as under [Evaluations](#evaluations).

- `contains`, `contains_any`, `contains_none`, `matches`, `matches_any` and `matches_none` are additive: two entries are two requirements, so the template's and the test's all stand.
- A lint rule, or a `words`, `lines`, `paths`, `urls` or `code` constraint, named on both sides is the template's entry with the test's parameters written over it, key by key: `words: {max: 600}` over a template's `words: {min: 50, max: 400}` gives `min: 50, max: 600`, while `count` and `except` under `paths`, `urls` or `code` are replaced whole. A lint takes the test's severity, a bare name being `error`; a constraint takes it where the test writes one, else the template's. When the template has several entries of that name, the test's parameters override each of them; when the test has several, each overrides in turn and one entry remains.
- The nearest `format` wins: the test's own replaces its templates' one, severity included, and a later template in `uses` replaces an earlier one.

### Evaluations

- `model`, `max_tokens` and `max_budget_usd` are the test's own where it writes one, else those of the last template in `uses` that does. So is each key of `setup`, one by one: a test writing only `working_folder` keeps the template's `harness`. A list is one value: a test's `skills` replaces the template's list whole.
- What an evaluation must hold is checked once merged: a template can bring the `task`, the `model` or the `harness`, and a template's `override_system_prompt` clashes with a test's `append_system_prompt`.
- Tasks chain: a template's `task` and the test's are two tasks. The templates' run first, in `uses` order, then the test's, in the same workspace and conversation.
- An `expect` is checked on the task written beside it, right after that task. One with no task beside it, in a template holding none or in a test whose task comes from its templates, is checked on the nearest task above it in the chain; one with no task above it is a load error.
- Where several `expect` land on the same task, the checks of their `response` blocks merge as the `constraints` of a static check do, above, a block's `severity` counting as written on each of its checks, and so do those of the `file` blocks of the same `with_path`. A file has to exist at `error` unless every block naming it says `warn`, the template's and the test's alike.
