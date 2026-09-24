# Checks

A `static-check` test runs its checks against each case's prompt, without a model. There are three families: [`lint`](#lint), [`format`](#format) and [`constraints`](#constraints). Every check runs and reports; a check reports one finding per offending item (character, link, path, word, pattern, URL, block) and one for a count out of bounds.

A prompt file that cannot be read (missing, not UTF-8) or that opens a `---` frontmatter block on line 1 that never closes makes its case `ERROR`, with every check skipped.

## Check entries

An entry is a bare name when it takes no parameters, and a one-key mapping of the name to its parameters otherwise. An unknown name or parameter is a load error.

### `severity`

Accepted by every entry: `error`, the default, or `warn`. A finding of an `error` check fails the case. A finding of a `warn` check is reported and never fails; a case whose only findings are warnings passes.

### Bounds

A bound is `min`, `max` or both: non-negative integers (a YAML boolean is not one), `min` at most `max`. `words` and `lines` take them directly; other checks nest them under `count` or `occurrences`.

## `lint`

A list of built-in rules with nothing to configure. Naming a rule twice in a test is a load error; a rule named in a template and in the test [merges](templates.md#merging).

### `chars`

No invisible characters, exactly these seven: `U+FEFF` (byte order mark, or zero-width no-break space mid-file), `U+00A0` (no-break space), `U+202F` (narrow no-break space), `U+200B` (zero width space), `U+200C` (zero width non-joiner), `U+200D` (zero width joiner) and `U+2060` (word joiner). Every other character passes. One finding per occurrence, with its line and codepoint.

### `markdown_links`

Every inline link and image resolves. A target starting with `/` resolves from the project root, and is a finding in a file without `root`; any other from the prompt file's directory. A `#anchor` must match a heading of the target, or of the prompt itself for a bare `#anchor`; headings are compared as GitHub slugs, with `-1`, `-2` for duplicates. A target with a URL scheme (two letters or more, then `:`, as `https:` or `mailto:`) is not checked. Reference-style links, links in fenced blocks and links in inline code spans are not checked. Skipped for a `text` prompt.

### `paths_exist`

Every [detected path](#paths-1) exists, a directory counting as a file: a relative path from the prompt file's directory, a `/` or `~/` path as absolute. Skipped for a `text` prompt.

## `format`

One entry naming a file format; any other name is a load error. What each format asserts is not specified yet: the check always passes.

### `anthropic-skill`

The format of a skill's `SKILL.md`.

### `anthropic-claude`

The format of a `CLAUDE.md`.

## `constraints`

A list of checks with the thresholds, word lists and policies the user sets; nothing runs unless listed. A constraint may appear more than once, each entry a separate check.

### `words`

The whitespace-separated words of the whole file, frontmatter included, within a [bound](#bounds).

### `lines`

The lines of the file, blank ones included, within a bound. An empty file has 0 lines.

### `contains`

Each word of `words` occurs within `occurrences`: at least once when it is omitted.

### `contains_any`

The total occurrences of the words of `words` fall within `occurrences`: at least one when it is omitted.

### `contains_none`

No word of `words` occurs. One finding per word found. Takes no `occurrences`.

### `matches`

Each pattern of `patterns` matches within `occurrences`: at least once when it is omitted.

### `matches_any`

The total matches of the patterns of `patterns` fall within `occurrences`: at least one when it is omitted.

### `matches_none`

No pattern of `patterns` matches. One finding per pattern found. Takes no `occurrences`.

### `paths`

The [detected paths](#paths-1). With no parameters it only reports what it detected.

- `except`: one glob or a list, in the [glob syntax](test-file.md#globs), matched against the whole path. Matching paths are removed from the check, and still reported as detected.
- `style`: `posix` or `windows`. A remaining path written with the other convention's separator is a finding.
- `count`: a bound on how many paths remain.

### `urls`

The [detected URLs](#urls-1).

- `count`: a bound on how many there are. `count: {max: 0}` bans URLs.
- `default`: `allow` or `deny`, the policy for every host not in `except`.
- `except`: one host or a list, getting the opposite of `default`. A host includes its subdomains. `default` is required when `except` is given.

### `code`

The [fenced blocks](#fenced-blocks); inline code spans are not blocks.

- `count`: a bound on how many there are. `count: {max: 0}` bans code.
- `default`: `allow` or `deny`, the policy for every language not in `except`.
- `except`: a language or a list, getting the opposite of `default`. `not_specified` stands for a block with no tag. Tags match as written, case-insensitively, never inferred from the contents: `sh`, `shell` and `bash` are three tags. `default` is required when `except` is given.

### `occurrences`

On `contains`, `contains_any`, `matches` and `matches_any`: an exact integer, or a bound mapping; the two spellings are exclusive. Omitted, it means at least one. Matches are counted without overlap.

### `words` and `patterns` lists

The `contains*` checks take their list under `words`, the `matches*` checks under `patterns`: one entry, a list, or a path to a file holding one entry per line. A single string is a path when it contains `/`, patterns included, and resolves like any path in the test file; list entries are never paths. In a file, blank lines are ignored, each entry is stripped of surrounding whitespace, a leading byte order mark is dropped, and there is no comment syntax. An empty list or a blank entry is a load error. With no other parameter, the list may be given directly as the check's value.

### `case_sensitive`

On the `contains*` checks: `true` or `false`, the default. Words match on `\w` boundaries, case-insensitively unless `case_sensitive` is `true`. A multi-word entry matches as a phrase, its whitespace as written.

### Patterns

Python `re` with `MULTILINE` on, so `^` and `$` apply per line. No implicit case folding: write `(?i)`. An invalid pattern is a load error naming it.

## Detection

Path and URL detection is heuristic, so `paths`, `paths_exist` and `urls` report everything they detected, findings or not; it prints with `-v`.

### Fenced blocks

Three or more backticks or tildes open a block. The closing fence is the same character, at least as long; an unclosed block runs to the end of the file. The tag is the first word after the opening fence, lowercased, or `not_specified` when there is none. Indented code blocks are not fences.

### Paths

Detected outside fenced blocks, inline code spans included. A token is a path when it contains `/` or `\`, holds no `://`, and either starts with `./`, `../`, `/`, `~/` or a drive letter, ends with `/`, or has a dot in its last segment. So `and/or` and a bare `src/skilleval` are not paths. Trailing `.,:;` and surrounding backticks, quotes, parentheses and square brackets are stripped; angle brackets stay, since they mark placeholders.

### URLs

Detected everywhere, fenced blocks included: `http://` or `https://` followed by non-space characters, with trailing punctuation (`.,;:!?`, closing quotes, brackets and backticks) stripped. The host is lowercased, without port and without credentials; a bracketed host that is not an IPv6 address, such as `[your-host]`, keeps its brackets.
