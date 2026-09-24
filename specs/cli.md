# CLI

A thin wrapper over the same public API, mirroring pytest: same argument forms, node ids, selection flags and exit codes.

```
skilleval                                      # everything
skilleval evals/skills/                        # a directory
skilleval evals/skills.eval.yml::house-style   # one test
skilleval -k refactor -x -q
```

```python
from skilleval import ExitCode, main
main(["-k", "refactor"]) == ExitCode.OK
```

`main` and `ExitCode` are the whole public API, as with pytest; result objects stay internal until someone needs them.

## Options

- positional arguments — paths, or node ids as defined in [README.md](README.md), which `-k` also matches against
- `-k WORD` — keep only cases whose node id contains that text. Plain substring, not pytest's boolean expressions; those come if someone asks
- `-x` — stop at the first failure or error
- `-q` / `-v` — `-q` prints only the failure and error sections and the summary; `-v` prints one line per case
- `--collect-only` — list node ids, run nothing
- `--version`

## Discovery

A directory argument collects `*.eval.yml` and `*.eval.yaml` recursively in sorted order, skipping dot-directories and vendored ones (`node_modules`, `venv`, `site-packages`) — ordinary YAML such as CI workflows is never a candidate. A file named explicitly is always collected, whatever it is called, and a case named twice is collected once. Paths in node ids are posix and relative to the current directory, in the file part and in the brackets alike.

Every collected file must be a skilleval file: all top-level keys known, and at least one of `tests` or `templates`. Anything else is an error naming the file, so a misspelled `test:` fails loudly instead of disappearing. A template-only file is valid and contributes no tests. A duplicate key anywhere in the file is a load error, since a silently dropped test id is the worst failure a test tool can have.

## Output

A progress character per case by default, one line per case with `-v`. Findings print indented under their case as `check: message`, with the line where the check has one and `[warn]` after a warning. A case whose only findings are warnings is `PASSED`; the summary counts one warning per warned check entry per case. `SKIPPED` says why; `ERROR` is a case that could not run and says how many checks went with it.

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

Pytest's: `0` passed, `1` failures or errors, `2` a load error in a collected file (pytest's collection error), `3` internal error, `4` usage error (unknown flag, path or node id not found), `5` nothing collected — an empty run is loud, not green. Warnings never affect the exit code.
