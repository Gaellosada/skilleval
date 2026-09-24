# skilleval

## Layout

```
specs/              design specs — README.md is the entry point
  cli.md              CLI, discovery, node ids, exit codes
  templates.md        reusable test bodies and how they merge
  static-checking.md  static checks: lint, format, constraints
  examples/           worked test files
src/skilleval/      the package
  testfile/           a test file read into dataclasses: load, checks, templates, paths
  static/             the static-check kind: prompt extraction, lint, formats, constraints
  runner.py           collection, node ids, needs
  report.py           terminal output
  cli.py              main and ExitCode, the public API
tests/
  unit/               one directory per package, one file per module with behaviour
  integration/        runner, CLI and a fixture project end to end
docs/               user-facing documentation, one entry per keyword (with the implementation)
```

## Commands

```
pip install -e .[dev]   # the package and pytest
pytest -q               # the suite
skilleval evals/        # run the tests in a directory
```
