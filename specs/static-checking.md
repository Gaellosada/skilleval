# Static checks

Checks on a prompt that run without invoking a model — deterministic, no harness, no cost. They are a `kind: static-check` test, which names a `prompt` and reports a result per file matched; the test file itself is described in [README.md](README.md).

## Lint

Built-in rules with nothing to configure: on or off, same verdict in every repo. Named as a plain list.

```yaml
lint: [chars, markdown_links, paths_exist]
```

- `chars` — no invisible characters, exactly these seven:
    - `U+FEFF` byte order mark, and a zero-width no-break space when it appears mid-file
    - `U+00A0` no-break space, `U+202F` narrow no-break space
    - `U+200B` zero width space, `U+200C` zero width non-joiner, `U+200D` zero width joiner, `U+2060` word joiner

  Everything else passes, including smart quotes (fine in prose), CRLF (normal on Windows), tabs and emoji. One finding per occurrence, reporting the line and the escaped codepoint.
- `markdown_links` — every markdown link resolves: relative targets point at a real file, `#anchors` match a heading in the target. `http(s)` links are left to `urls`.
- `paths_exist` — every path mentioned exists: relative ones from the prompt file's directory, `/` and `~/` ones as absolute, a directory counting as much as a file. Paths inside fenced code blocks are skipped, since that is where placeholders like `path/to/file.py` live.

`markdown_links` and `paths_exist` need a file-backed prompt and are skipped only for a `text` one.


## Format

Lint in nature — built in, maintained internally, nothing to tune — but it names *which* format, so it is its own key rather than an entry in the `lint` list.

```yaml
format: anthropic-skill

format:                          # with parameters, like any check entry
  anthropic-skill:
    severity: warn
```

Asserts the conventions of the named format, built in so they track upstream changes; user-defined formats are out of scope. Supported names: `anthropic-skill` (`SKILL.md`) and `anthropic-claude` (`CLAUDE.md`). What each asserts is specified later; until then the key is validated — an unknown name is a load error — and the check passes.

## Constraints

Everything the user decides — thresholds, word lists, policies. No defaults, nothing runs unless asked.

```yaml
constraints:
  - words:
      max: 400
  - paths:
      style: posix
  - urls:
      default: deny
      except: [docs.anthropic.com]
```

- `words` — `len(text.split())` over the whole file, frontmatter included, since that is what the model reads. Bounded by `min` and/or `max`.
- `lines` — `len(text.splitlines())`, blanks included, so an empty file has 0 lines. Bounded by `min` and/or `max`.
- `contains` — every word in the list appears. `occurrences` bounds how many times each one does.
- `contains_any` — at least one of them appears. `occurrences` bounds the total across the list.
- `contains_none` — none of them appear (banned words).
- `matches`, `matches_any`, `matches_none` — the same three against regular expressions instead of words, `occurrences` included.
- `paths` — the file paths mentioned in the prompt; with no parameters it only reports what it detected. `except` removes placeholders such as `path/to/file.py` from the check, though they stay in what it reports as detected; `style: posix | windows` fails the rest on the other convention; `count` bounds how many remain.
- `urls` — the URLs in the prompt. `count` bounds how many (`count: {max: 0}` bans them outright). Host filtering reads as one sentence, `default: allow | deny` plus `except: [hosts]` — `{ default: deny, except: [docs.anthropic.com] }` is a whitelist, `{ default: allow, except: [localhost] }` a blacklist. `default` is required whenever `except` is given, so the polarity is never implicit. Subdomains are included.
- `code` — the fenced code blocks in the prompt; inline spans are not counted. `count` bounds how many, so `count: {max: 0}` disallows code entirely. Languages filter like `urls` hosts, `default: allow | deny` plus `except: [languages]`, with `not_specified` as the entry for an untagged block: `{ default: deny, except: [bash, not_specified] }` permits shell and untagged code only, `{ default: allow, except: [not_specified] }` requires every block to declare a language. The language is the fence tag as written, never inferred from the contents, and tags match literally (case-insensitively): `sh`, `shell` and `bash` are three tags, so list every variant you accept. A block tagged as the wrong language is out of reach: these checks catch mistakes and drift, not evasion.

Lint and constraints are independent gates; both must pass. A check reports one finding per offending item — word, pattern, path, URL, block, character — and one for a count out of bounds.

A check whose only job is counting takes `min`/`max` directly (`words`, `lines`); one that counts alongside other parameters nests them under `count`, and occurrence bounds are always `occurrences`. Bounds are non-negative integers (a YAML boolean is not one) with `min` at most `max`.

`occurrences` is either an exact number — `occurrences: 4` requires exactly four — or a mapping with `min`, `max` or both; the two spellings are exclusive. Omitted on `contains`, `contains_any`, `matches` or `matches_any`, it means at least one match. Written with neither a number nor a bound it is an error, as it is on `contains_none` and `matches_none`, where the count is zero by definition.

The `contains*` checks take their list under `words` and the `matches*` checks take theirs under `patterns`: a single entry, an inline list, or a path to a file holding one per line — blank lines ignored, no comment syntax, the path resolving like any other. A single string is a path when it contains a `/`; list entries are always words. An empty list is an error. A check with no other parameters may give the list directly, as `contains: Usage`.

Words match case-insensitively on `\w` boundaries unless `case_sensitive: true`, so `Usage` matches `Usage:` but not `Usages`; a multi-word entry matches as a phrase. Patterns are Python `re` with `MULTILINE` on, so `^## [A-Z]` applies per line, and occurrences are counted without overlap; there is no implicit case folding, users write `(?i)`, and an invalid pattern is a load error naming it.

## Detection

Path and URL detection is heuristic, so both report everything they detected, not just the failures — a mis-detection is then visible rather than silently counted.

**Fenced blocks.** Three or more backticks or tildes open a block; the closing fence is the same character, at least as long, and an unclosed fence runs to end of file. The tag is the first word after the opening fence, lowercased, or `not_specified` when there is none. Indented code blocks are not fences, and inline spans are never blocks.

**Paths.** A token is a path when it contains `/` or `\`, holds no `://`, and either starts with `./`, `../`, `/`, `~/` or a drive letter, ends with `/`, or has a dot in its last segment. So `and/or` and a bare `src/skilleval` are not paths — the latter means `paths_exist` does not verify directory references written that way. Trailing `.,:;)` and surrounding backticks, quotes, parentheses or square brackets are stripped; angle brackets stay, since they mark placeholders. Inline code spans count, fenced blocks do not. `except` patterns use the glob syntax of `exclude` on a prompt: `*`, `?` and `[...]` stop at a separator, `**` crosses them, no negation, matched against the whole token.

**URLs.** `https?://` followed by non-space characters, trailing punctuation (`.,;:!?`, closing quotes, brackets and backticks) stripped, fenced blocks included — a `curl` line is exactly what a host policy cares about. The host is the netloc lowercased, without port and without any credentials before `@`. A subdomain matches its parent.

**Markdown links.** Inline `[text](target)` and images only; reference-style links are never checked. Links inside fenced blocks are skipped. Anchors use GitHub slugs, with `-1`, `-2` for duplicates. A target starting with `/` resolves from the project root, everything else from the file's directory; a `/` target in a test that declares no `root` is a finding.

## Low priority

Only once everything above is done.

- `format` for `agents-md` (`AGENTS.md`) — the vendor-neutral file other harnesses read.
- `format` for Claude Code slash commands (`.claude/commands/*.md`) and subagents (`.claude/agents/*.md`) — same extractor, small frontmatter schema each.

Rule for any new format: only if it has a written upstream spec to point at.

Worked examples: [examples/static-test.eval.yml](examples/static-test.eval.yml) and the templates it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
