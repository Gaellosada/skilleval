# skilleval

## Layout

```
specs/              design specs — README.md is the entry point
  cli.md              CLI, discovery, node ids, exit codes
  templates.md        reusable test bodies and how they merge
  static-checking.md  static checks: lint, format, constraints
  examples/           worked test files
src/skilleval/      the package
tests/              pytest suite
docs/               user-facing documentation, one entry per keyword
```

## Commands

```
pip install -e .[dev]   # the package and pytest
pytest -q               # the suite
skilleval evals/        # run the tests in a directory
```
