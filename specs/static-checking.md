# Static checks

Checks on a prompt that run without invoking a model — deterministic, no harness, no cost. They are a `kind: static-check` test, which names a `prompt` and reports a result per file matched; the test file itself is described in [README.md](README.md).

## Lint

Built-in rules with nothing to configure: on or off, same verdict in every repo. Named as a plain list.

```yaml
lint: [chars, markdown_links, paths_exist]
```

- `chars` — no invisible characters: BOM, non-breaking spaces, zero-width characters. These three are always defects, whereas smart quotes (fine in prose) and CRLF (normal on Windows) are deliberately not covered. Reports the line and the escaped codepoint.
- `markdown_links` — every markdown link resolves: relative targets point at a real file, `#anchors` match a heading in the target. `http(s)` links are left to `urls`.
- `paths_exist` — every path mentioned resolves to a real file, relative to the prompt file's directory. Paths inside fenced code blocks are skipped, since that is where placeholders like `path/to/file.py` live.

`markdown_links` and `paths_exist` need a file-backed prompt and are skipped only for a `text` one.


## Format

Lint in nature — built in, maintained internally, nothing to tune — but it names *which* format, so it is its own key rather than an entry in the `lint` list.

```yaml
format: anthropic-skill

format:                          # with parameters, like any check entry
  anthropic-skill:
    severity: warn
```

Asserts required frontmatter fields, heading structure and section order for the named format. Built in so they can track upstream changes; user-defined formats are out of scope for now. Supported: `anthropic-skill` (`SKILL.md`) and `anthropic-claude` (`CLAUDE.md`, conventions only — the file has no frontmatter or required sections). What each one asserts, field by field, is specified later.

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
- `contains` — every word in the list appears. `occurrences` bounds how many times each one does (default `min: 1`).
- `contains_any` — at least one of them appears. `occurrences` bounds the total across the list.
- `contains_none` — none of them appear (banned words).
- `matches`, `matches_any`, `matches_none` — the same three against regular expressions instead of words, `occurrences` included.
- `paths` — the file paths mentioned in the prompt. `style: posix | windows` fails on the other convention; `count` bounds how many there are; `ignore` exempts placeholders such as `path/to/file.py`.
- `urls` — the URLs in the prompt. `count` bounds how many (`count: {max: 0}` bans them outright). Host filtering reads as one sentence, `default: allow | deny` plus `except: [hosts]` — `{ default: deny, except: [docs.anthropic.com] }` is a whitelist, `{ default: allow, except: [localhost] }` a blacklist. `default` is required whenever `except` is given, so the polarity is never implicit. Subdomains are included.
- `code` — the fenced code blocks in the prompt; inline spans are not counted. `count` bounds how many, so `count: {max: 0}` disallows code entirely. Languages filter like `urls` hosts, `default: allow | deny` plus `except: [languages]`, with `not_specified` as the entry for an untagged block: `{ default: deny, except: [bash, not_specified] }` permits shell and untagged code only, `{ default: allow, except: [not_specified] }` requires every block to declare a language. The language is the fence tag as written, never inferred from the contents, and tags match literally (case-insensitively): `sh`, `shell` and `bash` are three tags, so list every variant you accept. A block tagged as the wrong language is out of reach: these checks catch mistakes and drift, not evasion.

Lint and constraints are independent gates; both must pass.

A check whose only job is counting takes `min`/`max` directly (`words`, `lines`); one that counts alongside other parameters nests them under `count`, and occurrence bounds are always `occurrences`.

The `contains*` checks take their list under `words` and the `matches*` checks take theirs under `patterns`: a single entry, an inline list, or a path to a file holding one per line — blank lines ignored, no comment syntax, the path resolving like any other. A check with no other parameters may give the list directly, as `contains: Usage`.

Words match case-insensitively on `\w` boundaries unless `case_sensitive: true`, so `Usage` matches `Usage:` but not `Usages`; a multi-word entry matches as a phrase. Patterns are Python `re` with `MULTILINE` on, so `^## [A-Z]` applies per line; there is no implicit case folding, users write `(?i)`, and an invalid pattern is a load error naming it.

Path and URL detection is heuristic, so both report everything they detected, not just the failures — a mis-detection is then visible rather than silently counted.

## Low priority

Only once everything above is done.

- `format` for `agents-md` (`AGENTS.md`) — the vendor-neutral file other harnesses read.
- `format` for Claude Code slash commands (`.claude/commands/*.md`) and subagents (`.claude/agents/*.md`) — same extractor, small frontmatter schema each.

Rule for any new format: only if it has a written upstream spec to point at.

Worked examples: [examples/static-test.eval.yml](examples/static-test.eval.yml) and the templates it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
