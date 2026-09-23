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

## Exit codes

Pytest's: `0` passed, `1` failures, `2` interrupted, `3` internal error, `4` usage error, `5` nothing collected — an empty run is loud, not green. Warnings never affect the exit code.
