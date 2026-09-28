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
- `markdown_links` — every markdown link resolves: relative targets point at a real file, `#anchors` match a heading in the target. A link with a URL scheme (`https:`, `mailto:`, ...; two letters or more, so `C:/` stays a path) is left alone; only `http(s)` ones go to `urls`.
- `paths_exist` — every path mentioned exists: relative ones from the prompt file's directory, `/` and `~/` ones as absolute, a directory counting as much as a file. Paths inside fenced code blocks are skipped, since that is where placeholders like `path/to/file.py` live.

`markdown_links` and `paths_exist` need a file-backed prompt and are skipped only for an inline one.


## Format

Lint in nature — built in, maintained internally, nothing to tune — but it names *which* format, so it is its own key rather than an entry in the `lint` list.

```yaml
format: anthropic-skill

format:                          # with parameters, like any check entry
  anthropic-skill:
    severity: warn
```

Asserts the conventions of the named format, built in so they track upstream changes; user-defined formats are out of scope. Supported names: `anthropic-skill` (`SKILL.md`) and `anthropic-claude` (`CLAUDE.md`); an unknown name is a load error.

A format asserts only what Anthropic documents as a hard rule, one a file either meets or breaks. Its advice — a `SKILL.md` body under 500 lines, a `CLAUDE.md` under 200, a description in the third person — is a threshold or a judgement, so it belongs to `constraints` or to nobody. One finding per rule broken, naming what it is about, a field, the file or the frontmatter, and the value unless the rule is about a length or a size; none carries a line. A rule is one item of a list below, or one clause between semicolons in a table: a name with a capital and two hyphens in a row breaks one rule, once. A rule about the file, its name or its directory, needs a file-backed prompt and does not apply to an inline one.

### `anthropic-skill`

From the [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), the [Agent Skills specification](https://agentskills.io/specification), the frontmatter reference of [Claude Code's skills](https://code.claude.com/docs/en/skills#frontmatter-reference) and the validator Anthropic packages skills with, [`quick_validate.py`](https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py). Where they differ, a value follows the strictest — Claude Code makes `name` optional, the specification requires it — and a field may be any that one of them documents, so a skill that passes loads in Claude Code, and uploads to claude.ai and the API when it keeps to the six fields of the specification. The other way round does not hold: Claude Code loads skills that fail here, one named `claude-helper` or one with a field of its author's, since it enforces less than the other two.

- The file is named `SKILL.md`.
- The frontmatter is there: the first line is `---` and a later line is `---`. Without it nothing below is checked.
- The frontmatter is a YAML mapping. When it does not parse, a date that does not exist included, or is anything else, nothing below is checked.
- Every field is a documented one. The specification has `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`; Claude Code adds `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths` and `shell`. One finding per other field: an upload refuses it, and Claude Code ignores it without a word, which is how a misspelt `when-to-use` goes unnoticed.
- `name` and `description` are there: one finding for each that is missing.
- Every field has the type of its row below, what the mapping holds included; the other rules of a field apply to a value of that type. A field written without a value is null, so of no type.

| Field | Type | Rules |
|---|---|---|
| `name` | string | at most 64 characters; lowercase letters `a-z`, digits and hyphens only, at least one character, no hyphen first, last or twice in a row; holds neither `anthropic` nor `claude`, as written, a capital being the business of the clause before; is the name of the directory holding the file |
| `description` | string | not blank; at most 1024 characters; no `<` and no `>` — the documentation forbids XML tags, the validator either character |
| `compatibility` | string | 1 to 500 characters |
| `license`, `when_to_use`, `argument-hint`, `model`, `agent` | string | |
| `metadata` | mapping | string keys and string values |
| `hooks` | mapping | |
| `allowed-tools`, `disallowed-tools`, `arguments`, `paths` | string, or list of strings | the specification has `allowed-tools` as a string only, and as experimental, its support varying; Claude Code's reading holds |
| `disable-model-invocation`, `user-invocable`, `background` | boolean | `true`, `false`, `yes`, `no`, `on`, `off`, `1` or `0`, in any letter case, quoted or not |
| `effort` | string | `low`, `medium`, `high`, `xhigh` or `max`, as written |
| `context` | string | `fork` |
| `shell` | string | `bash` or `powershell` |

The body is free: the specification puts no restriction on it.

### `anthropic-claude`

From [Claude Code's memory page](https://code.claude.com/docs/en/memory), which asks for no structure: no frontmatter, no heading. Two rules are left.

- The file is named `CLAUDE.md` or `CLAUDE.local.md`, the names Claude Code loads.
- The text is at most 4 MiB, 4 × 2²⁰ bytes as UTF-8: Claude Code skips a larger file.

`@path` imports are not checked: nothing tells an import from a mention such as `@types/node`, and the documentation does not make a missing one an error.

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
- `urls` — the URLs in the prompt. `count` bounds how many (`count: {max: 0}` bans them outright). Host filtering reads as one sentence, `default: allow | deny` plus `except`, one host or a list — `{ default: deny, except: [docs.anthropic.com] }` is a whitelist, `{ default: allow, except: [localhost] }` a blacklist. `default` is required whenever `except` is given, so the polarity is never implicit. Subdomains are included.
- `code` — the fenced code blocks in the prompt; inline spans are not counted. `count` bounds how many, so `count: {max: 0}` disallows code entirely. Languages filter like `urls` hosts, `default: allow | deny` plus `except: [languages]`, with `not_specified` as the entry for an untagged block: `{ default: deny, except: [bash, not_specified] }` permits shell and untagged code only, `{ default: allow, except: [not_specified] }` requires every block to declare a language. The language is the fence tag as written, never inferred from the contents, and tags match literally (case-insensitively): `sh`, `shell` and `bash` are three tags, so list every variant you accept. A block tagged as the wrong language is out of reach: these checks catch mistakes and drift, not evasion.

Lint and constraints are independent gates; both must pass. A check reports one finding per offending item — word, pattern, path, URL, block, character — and one for a count out of bounds.

A check whose only job is counting takes `min`/`max` directly (`words`, `lines`); one that counts alongside other parameters nests them under `count`, and occurrence bounds are always `occurrences`. Bounds are non-negative integers (a YAML boolean is not one) with `min` at most `max`.

`occurrences` is either an exact number — `occurrences: 4` requires exactly four — or a mapping with `min`, `max` or both; the two spellings are exclusive. Omitted on `contains`, `contains_any`, `matches` or `matches_any`, it means at least one match. Written with neither a number nor a bound it is an error, as it is on `contains_none` and `matches_none`, where the count is zero by definition.

The `contains*` checks take their list under `words` and the `matches*` checks take theirs under `patterns`: a single entry, an inline list, or a path to a file holding one per line — blank lines ignored, each entry stripped of surrounding whitespace and a leading byte-order mark dropped, no comment syntax, the path resolving like any other. A single string is a path when it contains a `/`; list entries are always words. An empty list or a blank entry is an error. A check with no other parameters may give the list directly, as `contains: Usage`.

Words match case-insensitively on `\w` boundaries unless `case_sensitive: true`, so `Usage` matches `Usage:` but not `Usages`; a multi-word entry matches as a phrase, its whitespace as written. Patterns are Python `re` with `MULTILINE` on, so `^## [A-Z]` applies per line, and occurrences are counted without overlap; there is no implicit case folding, users write `(?i)`, and an invalid pattern is a load error naming it.

## Detection

Path and URL detection is heuristic, so both report everything they detected, not just the failures, and `code` reports the tag of every block — a mis-detection is then visible rather than silently counted.

**Fenced blocks.** Three or more backticks or tildes open a block; the closing fence is the same character, at least as long, and an unclosed fence runs to end of file. The tag is the first word after the opening fence, lowercased, or `not_specified` when there is none. Indented code blocks are not fences, and inline spans are never blocks.

**Paths.** A token is a path when it contains `/` or `\`, holds no `://`, and either starts with `./`, `../`, `/`, `~/` or a drive letter, ends with `/`, or has a dot in its last segment. So `and/or` and a bare `src/skilleval` are not paths — the latter means `paths_exist` does not verify directory references written that way. Trailing `.,:;)` and surrounding backticks, quotes, parentheses or square brackets are stripped; angle brackets stay, since they mark placeholders. Inline code spans count, fenced blocks do not. `except` patterns use the glob syntax of `exclude` on a prompt: `*`, `?` and `[...]` stop at a separator, `**` crosses them, matched against the whole token. A class reads as in `fnmatch`: `[!...]` negates, ranges stay, a leading `^` and a backslash are literal, and an unclosed `[` is literal; a glob that does not compile, such as `[z-a]`, is a load error naming it.

**URLs.** `https?://` followed by non-space characters, trailing punctuation (`.,;:!?`, closing quotes, brackets and backticks) stripped, fenced blocks included — a `curl` line is exactly what a host policy cares about. The host is the netloc lowercased, without port and without any credentials before `@`; a bracketed host that is not an IPv6 address, such as a `[your-host]` placeholder, keeps its brackets. A subdomain matches its parent.

**Markdown links.** Inline `[text](target)` and `[text](target "title")`, and images, only; reference-style links are never checked. Links inside fenced blocks are skipped. Links inside inline code spans are skipped too. Anchors use GitHub slugs, with `-1`, `-2` for duplicates. A target starting with `/` resolves from the project root, everything else from the file's directory; a `/` target in a test that declares no `root` is a finding.

## Low priority

Only once everything above is done.

- `format` for `agents-md` (`AGENTS.md`) — the vendor-neutral file other harnesses read.
- `format` for Claude Code slash commands (`.claude/commands/*.md`) and subagents (`.claude/agents/*.md`) — same extractor, small frontmatter schema each.

Rule for any new format: only if it has a written upstream spec to point at.

Worked examples: [examples/static-test.eval.yml](examples/static-test.eval.yml) and the templates it uses in [examples/shared-templates.eval.yml](examples/shared-templates.eval.yml).
