# skilleval documentation

skilleval runs declarative tests, written in YAML test files, against the prompts of an LLM setup such as skills and `CLAUDE.md` files. The one kind of test today is `static-check`: it reads a prompt as text and checks it without running a model.

- [test-file.md](test-file.md) — the test file: `root`, `tests`, `kind`, `prompt`, `needs`, and how paths resolve.
- [templates.md](templates.md) — `templates` and `uses`: reusable checks and how they merge.
- [checks.md](checks.md) — `lint`, `format` and `constraints`, their parameters, and how paths, URLs and code blocks are detected.
- [cli.md](cli.md) — the `skilleval` command: arguments, node ids, options, output, exit codes and the Python API.

## Keywords

- Test file: [`root`](test-file.md#root), [`tests`](test-file.md#tests), [`templates`](templates.md#templates).
- Test: [`kind`](test-file.md#kind), [`prompt`](test-file.md#prompt), [`needs`](test-file.md#needs), [`uses`](templates.md#uses), [`lint`](checks.md#lint), [`format`](checks.md#format), [`constraints`](checks.md#constraints).
- Prompt: [`text`](test-file.md#text), [`include`](test-file.md#include), [`exclude`](test-file.md#exclude).
- Any check: [`severity`](checks.md#severity).
- Lint: [`chars`](checks.md#chars), [`markdown_links`](checks.md#markdown_links), [`paths_exist`](checks.md#paths_exist).
- Format: [`anthropic-skill`](checks.md#anthropic-skill), [`anthropic-claude`](checks.md#anthropic-claude).
- Constraints: [`words`](checks.md#words), [`lines`](checks.md#lines), [`contains`](checks.md#contains), [`contains_any`](checks.md#contains_any), [`contains_none`](checks.md#contains_none), [`matches`](checks.md#matches), [`matches_any`](checks.md#matches_any), [`matches_none`](checks.md#matches_none), [`paths`](checks.md#paths), [`urls`](checks.md#urls), [`code`](checks.md#code).
- Constraint parameters: [`min`, `max`](checks.md#bounds), [`count`](checks.md#bounds), [`occurrences`](checks.md#occurrences), [`words`, `patterns`](checks.md#words-and-patterns-lists), [`case_sensitive`](checks.md#case_sensitive), `except`, `default` and `style` under [`paths`](checks.md#paths), [`urls`](checks.md#urls) and [`code`](checks.md#code).
- Command line: [`-k`](cli.md#-k), [`-x`](cli.md#-x), [`-q`](cli.md#-q), [`-v`](cli.md#-v), [`--collect-only`](cli.md#--collect-only), [`--version`](cli.md#--version).
