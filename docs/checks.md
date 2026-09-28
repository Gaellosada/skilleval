# Checks

A `static-check` test runs its checks against each case's prompt, without a model. There are three families: [`lint`](#lint), [`format`](#format) and [`constraints`](#constraints). Every check runs and reports; a check reports one finding per offending item (character, link, path, word, pattern, URL, block) and one for a count out of bounds.

A prompt file that cannot be read (missing, not UTF-8) or that opens a `---` frontmatter block on line 1 that never closes makes its case `ERROR`, with every check skipped.

## Check entries

An entry is a one-key mapping of the name to its parameters, as `words: {max: 400}`, or the name alone when it gives none, as `chars`, the same as `chars: {}`; a `contains*` or `matches*` check may take its [list](#words-and-patterns-lists) directly. An unknown name or parameter is a load error.

### `severity`

Accepted by every entry: `error`, the default, or `warn`; a constraint that writes none and merges over a template's takes the template's, see [templates.md](templates.md#merging). A finding of an `error` check fails the case. A finding of a `warn` check is reported and never fails; a case whose only findings are warnings passes.

### Bounds

A bound is `min`, `max` or both: non-negative integers (a YAML boolean is not one), `min` at most `max`. `words` and `lines` take them directly; other checks nest them under `count` or `occurrences`.

## `lint`

A list of built-in rules with nothing to configure. Naming a rule twice in a test or a template is a load error; a rule named in a template and in the test [merges](templates.md#merging).

### `chars`

No invisible characters, exactly these seven: `U+FEFF` (byte order mark, or zero-width no-break space mid-file), `U+00A0` (no-break space), `U+202F` (narrow no-break space), `U+200B` (zero width space), `U+200C` (zero width non-joiner), `U+200D` (zero width joiner) and `U+2060` (word joiner). Every other character passes. One finding per occurrence, with its line and codepoint.

### `markdown_links`

Every inline link and image resolves. A target starting with `/` resolves from the project root, and is a finding in a file without `root`; any other from the prompt file's directory. A `#anchor` must match a heading of the target, or of the prompt itself for a bare `#anchor`; headings are compared as GitHub slugs, with `-1`, `-2` for duplicates. A target with a URL scheme (a letter, then one or more letters, digits, `+`, `.` or `-`, then `:`, as `https:` or `mailto:`) is not checked. Reference-style links, links in fenced blocks and links in inline code spans are not checked, nor is a link whose text holds a bracket or whose target holds a space. A target runs to its first `)`, so `foo(1).md` is checked as `foo(1`; a `"title"` after it is allowed. Only ATX (`#`) headings are anchors, and an anchor is compared as written, so `#Foo` matches no heading. Skipped for an inline prompt.

### `paths_exist`

Every [detected path](#paths-1) exists, a directory counting as a file: a relative path from the prompt file's directory, a `/` or `~/` path as absolute. `~user/` is not expanded, and a drive-letter path is a finding outside Windows. Skipped for an inline prompt.

## `format`

One entry naming a file format, as `format: anthropic-skill`, or `format: {anthropic-skill: {severity: warn}}` to set its [`severity`](#severity), the only parameter; any other name is a load error. A test's own `format` overrides its templates' ([merging](templates.md#merging)).

A format asserts what Anthropic documents as a hard rule, one a file meets or breaks. Its advice, such as a `SKILL.md` under 500 lines or a `CLAUDE.md` under 200, is for [`constraints`](#constraints), as `lines: {max: 200}`. One finding per rule broken, none with a line: it starts with the field when the rule is about one, and shows the value written when that is what to fix, a length or a size as its number. A rule is one item of a list below, or one clause between semicolons in the table. A rule about the file, its name or its directory, does not apply to an inline prompt.

### `anthropic-skill`

The format of a skill's `SKILL.md`, from the [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), the [Agent Skills specification](https://agentskills.io/specification), the frontmatter reference of [Claude Code](https://code.claude.com/docs/en/skills#frontmatter-reference) and [`quick_validate.py`](https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py), the validator Anthropic packages skills with, as they read on 2026-09-28.

Where they differ, a value follows the strictest and a field may be any that one of them documents. A skill that passes loads in Claude Code; it uploads to claude.ai and the API when it keeps to the six fields of the specification. Claude Code enforces less than the other two, so it loads skills that fail here, such as one named `claude-helper`.

- The file is named `SKILL.md`.
- The frontmatter is there: the first line is `---` and a later line is `---`. Without it, no rule below is checked. A file that opens it and never closes it makes its case `ERROR`, as for any check.
- The frontmatter is a YAML mapping. When it does not parse, or is anything else, no rule below is checked.
- Every field is one of the table below. One finding per other field, such as `version` or a misspelt `when-to-use`: an upload refuses it and Claude Code ignores it silently.
- `name` and `description` are there: one finding for each that is missing.
- Every field has the type of its row; its other rules apply to a value of that type. A field written without a value has none.

| Field | Type | Rules |
|---|---|---|
| `name` | string | at most 64 characters; lowercase letters `a-z`, digits and hyphens only, at least one character, no hyphen first, last or twice in a row; holds neither `anthropic` nor `claude`; is the name of the directory holding the file |
| `description` | string | not blank; at most 1024 characters; no `<` and no `>` |
| `compatibility` | string | 1 to 500 characters |
| `license`, `when_to_use`, `argument-hint`, `model`, `agent` | string | |
| `metadata` | mapping | string keys and string values, so `version: "1.0"`, quoted |
| `hooks` | mapping | |
| `allowed-tools`, `disallowed-tools`, `arguments`, `paths` | string, or list of strings | |
| `disable-model-invocation`, `user-invocable`, `background` | boolean | `true`, `false`, `yes`, `no`, `on`, `off`, `1` or `0`, in any letter case, quoted or not |
| `effort` | string | `low`, `medium`, `high`, `xhigh` or `max` |
| `context` | string | `fork` |
| `shell` | string | `bash` or `powershell` |

The six fields of the specification are `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`; Claude Code adds the others. The body is free.

### `anthropic-claude`

The format of a `CLAUDE.md`, from [Claude Code's memory page](https://code.claude.com/docs/en/memory) as it reads on 2026-09-28. The page asks for no structure, neither frontmatter nor headings, which leaves two rules.

- The file is named `CLAUDE.md` or `CLAUDE.local.md`.
- The text is at most 4 MiB, 4194304 bytes as UTF-8: Claude Code skips a larger file.

`@path` imports are not checked.

## `constraints`

A list of checks with the thresholds, word lists and policies the user sets; nothing runs unless listed. A constraint may appear more than once, each entry a separate check.

### `words`

The words of the whole file, frontmatter included, split at any whitespace as Python's `str.split` does, within a [bound](#bounds).

### `lines`

The lines of the file, as Python's `str.splitlines` counts them, blank ones included, within a bound. An empty file has 0 lines.

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
- `except`: one host or a list, getting the opposite of `default`. A host includes its subdomains and compares case-insensitively; an IPv6 host is written without brackets, as `::1`. `default` is required when `except` is given.

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

Path and URL detection is heuristic, so `paths`, `paths_exist` and `urls` report everything they detected, findings or not, and `code` the tag of every block; it prints with `-v`.

### Fenced blocks

Three or more backticks or tildes, indented by at most three spaces, open a block, unless a backtick fence has a backtick after it. The closing fence is the same character, at least as long, with nothing but whitespace after it; an unclosed block runs to the end of the file. The tag is the first word after the opening fence, lowercased, or `not_specified` when there is none. Indented code blocks are not fences.

### Paths

Detected outside fenced blocks, inline code spans included. A token is a path when it contains `/` or `\`, holds no `://`, and either starts with `./`, `../`, `/`, `~/` or a drive letter, ends with `/` or `\`, or has a dot in its last segment. So `and/or` and a bare `src/skilleval` are not paths. Tokens split at whitespace, parentheses and square brackets, so `src/foo(1).md` is not detected. Trailing `.,:;` are stripped, then surrounding backticks and quotes, so punctuation inside them stays; angle brackets stay, since they mark placeholders.

### URLs

Detected everywhere, fenced blocks included: `http://` or `https://`, lowercase, followed by non-space characters, with trailing `.,;:!?)]}>`, quotes and backticks stripped. The host is lowercased, without port and without credentials; a bracketed host that is not an IPv6 address, such as `[your-host]`, keeps its brackets.
