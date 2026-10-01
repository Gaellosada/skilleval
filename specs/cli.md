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

`main` and `ExitCode` are the whole public API, as with pytest; result objects stay internal until someone needs them. `main` reads `sys.argv[1:]` when given no list; `ExitCode` is an `IntEnum`.

## Options

- positional arguments — paths, or node ids as defined in [README.md](README.md), which `-k` also matches against
- `-k WORD` — keep only cases whose node id contains that text. Plain, case-sensitive substring, not pytest's boolean expressions; those come if someone asks
- `--static-checks` / `--evaluations` — keep only the cases of that kind, the `static-check` tests or the `evaluation` ones, on top of what the arguments and `-k` select. Giving both is a usage error: it asks for what no flag does. A kept test that `needs` one of the other kind is `SKIPPED` as `needs <id>, not selected`, like any test whose dependency was not selected; whatever needs that test in turn is skipped as `needs <that test>`
- `-x` — stop at the first failure or error; `collected N cases` still counts every case collected, as pytest's does
- `-q` / `-v` — `-q` prints only the failure and error sections and the summary; `-v` prints one line per case. Giving both is a usage error
- `--collect-only` — list node ids, run nothing
- `--version`

## Discovery

A directory argument collects `*.eval.yml` and `*.eval.yaml` recursively in sorted order, skipping dot-directories and vendored ones (`node_modules`, `venv`, `site-packages`) — ordinary YAML such as CI workflows is never a candidate. A file named explicitly is always collected, whatever it is called, and a case named twice is collected once. Paths in node ids are posix and relative to the current directory, in the file part and in the brackets alike.

Every collected file must be a skilleval file: all top-level keys known, and at least one of `tests` or `templates`. Anything else is an error naming the file, so a misspelled `test:` fails loudly instead of disappearing. A template-only file is valid and contributes no tests. A duplicate key anywhere in the file is a load error, since a silently dropped test id is the worst failure a test tool can have; the only keys that repeat are the top-level `tests` and `templates`, whose sections join ([README.md](README.md)), an id or a name in two of them still a load error.

## Output

The cases print as they run, each write flushed, as pytest's do: by default a file's name as its first case starts, then a progress character as each case ends; with `-v`, a case's node id as it starts, then its status and its lines as it ends; with `-q`, nothing until the end. What the run prints in all is the same as if it printed at the end. Findings print indented under their case as `check: message`, with the line where the check has one and `[warn]` after a warning; a message of several lines, such as the output ending a `run` failure, has them at the end of its first line, the rest following as written, and the reason of an `ERROR` likewise has its count of skipped checks at the end of its first line. A case whose only findings are warnings is `PASSED`; the summary counts one warning per warned check entry per case. `SKIPPED` says why, with `-v`; `ERROR` is a case that could not run and says how many checks went with it: every check of the test, those of an earlier task that ran included, and one for each file a task's `file` blocks name, which checks that it exists, since the case reports nothing of what they found. What a heuristic check detected prints under it only with `-v`.

```
$ skilleval evals/
collected 14 cases

evals/skills.eval.yml .F..E.s
evals/claude-md.eval.yml .......

=================================== FAILURES ===================================
evals/skills.eval.yml::house-style[.claude/skills/refactor/SKILL.md] FAILED
  words: 612 words, above the maximum of 400
  markdown_links: ./reference/api.md does not exist (line 84)
  paths_exist: src/cli.py does not exist (line 31) [warn]

==================================== ERRORS ====================================
evals/skills.eval.yml::house-style[.claude/skills/legacy/SKILL.md] ERROR
  frontmatter: unclosed --- block opened at line 1; 11 checks skipped

========= 1 failed, 11 passed, 1 skipped, 1 error, 2 warnings in 0.42s =========
```

```
$ skilleval evals/gates.eval.yml -v
collected 3 cases

evals/gates.eval.yml::house-style[.claude/skills/refactor/SKILL.md] FAILED
  words: 612 words, above the maximum of 400
evals/gates.eval.yml::root-instructions[CLAUDE.md] PASSED
evals/gates.eval.yml::exercises SKIPPED (needs house-style)

=================================== FAILURES ===================================
evals/gates.eval.yml::house-style[.claude/skills/refactor/SKILL.md] FAILED
  words: 612 words, above the maximum of 400

==================== 1 failed, 1 passed, 1 skipped in 0.12s ====================
```

Tests pin the status words, the finding shape and the counts — not the wording of any message.

## Exit codes

Pytest's codes, as `ExitCode` members: `0` `OK` passed, `1` `TESTS_FAILED` failures or errors, `2` `LOAD_ERROR` a load error in a collected file (pytest's collection error), `3` `INTERNAL_ERROR` internal error, `4` `USAGE_ERROR` usage error (unknown flag, `-q` with `-v`, `--static-checks` with `--evaluations`, path or node id not found), `5` `NO_TESTS_COLLECTED` nothing collected — an empty run is loud, not green. Warnings never affect the exit code.
