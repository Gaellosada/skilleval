# CLI

A thin wrapper over the same public API, mirroring pytest: same argument forms, node ids, selection flags and exit codes.

```
skilleval                                      # everything
skilleval evals/skills/                        # a directory
skilleval evals/skills.eval.yml::house-style   # one test
skilleval -k refactor -x -q
```

```python
from skilleval import main
main(["-k", "refactor"])
```

## Options

- positional arguments — paths, or node ids as defined in [README.md](README.md), which `-k` also matches against
- `-k WORD` — keep only cases whose node id contains that text. Plain substring, not pytest's boolean expressions; those come if someone asks
- `-x` — stop at the first failure
- `-q` / `-v` — quieter or more verbose output
- `--collect-only` — list node ids, run nothing
- `--version`

## Discovery

A directory argument collects `*.eval.yml` and `*.eval.yaml` recursively, skipping dot-directories and vendored ones — ordinary YAML such as CI workflows is never a candidate. A file named explicitly is always collected, whatever it is called.

Every collected file must be a skilleval file: all top-level keys known, and at least one of `tests` or `templates`. Anything else is an error naming the file, so a misspelled `test:` fails loudly instead of disappearing. A template-only file is valid and contributes no tests.

## Output

A progress character per case by default, one line per case with `-v`. Findings print indented under their case as `check: message`, with the line where the check has one and `[warn]` after a warning. A case whose only findings are warnings is `PASSED`. `SKIPPED` says why; `ERROR` is a case that could not run and says how many checks went with it.

```
$ skilleval evals/
collected 14 cases

evals/skills.eval.yml .F..E..                                            [ 50%]
evals/claude-md.eval.yml .......                                         [100%]

=================================== FAILURES ===================================
evals/skills.eval.yml::house-style[.claude/skills/refactor/SKILL.md] FAILED
  words: 612 words, above the maximum of 400
  markdown_links: ./reference/api.md does not exist (line 84)
  paths_exist: src/cli.py does not exist (line 31) [warn]

==================================== ERRORS ====================================
evals/skills.eval.yml::house-style[.claude/skills/legacy/SKILL.md] ERROR
  frontmatter: unclosed --- block opened at line 1; 11 checks skipped

============ 1 failed, 12 passed, 1 error, 2 warnings in 0.42s ============
```

```
$ skilleval evals/ -v -k refactor
evals/skills.eval.yml::house-style[.claude/skills/refactor/SKILL.md] FAILED
  words: 612 words, above the maximum of 400
evals/skills.eval.yml::root-instructions PASSED
evals/skills.eval.yml::exercises SKIPPED (needs house-style)
```

Tests pin the status words, the finding shape and the counts — not the wording of any message.

## Exit codes

Pytest's: `0` passed, `1` failures, `2` interrupted, `3` internal error, `4` usage error, `5` nothing collected — an empty run is loud, not green. Warnings never affect the exit code.
