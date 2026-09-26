# skilleval

Declarative, file-based tests for LLM setups — a harness, model, skills and config — and for single components such as one skill. Three kinds of test: `static-check` (reads a prompt as text, no model), `evaluation` (runs a setup against tasks) and `benchmark` (compares setups). Importable as a package; the CLI mirrors pytest.

## Layout

- `specs/` — the design specs. [specs/README.md](specs/README.md) is the entry point; [cli.md](specs/cli.md), [templates.md](specs/templates.md), [static-checking.md](specs/static-checking.md) and [evaluations.md](specs/evaluations.md) cover the CLI, templates, static checks and evaluations; [benchmarks.md](specs/benchmarks.md) is still to be written; `examples/` holds worked YAML. Read them before changing behaviour, and update them when a decision changes.
- `src/skilleval/` — the package: `cli.py`, `runner.py` and `report.py` at the top, `testfile/` loads a test file, `static/` runs the static checks.
- `tests/` — the pytest suite, `unit/` and `integration/`. Conventions in [tests/README.md](tests/README.md).
- `docs/` — user-facing documentation, one entry per keyword.

## Checks

`pip install -e .[dev]`, then `pytest -q`, `ruff check` and `mypy` (strict, over `src/`) must all pass. CI runs them on pushes to `main` and on pull requests, in two jobs, `lint` and `test`, and the `test` job sends coverage to SonarQube Cloud ([sonar-project.properties](sonar-project.properties)).

## Bar

This is meant to be a professional tool, so the code has to read that way: concise, readable, high quality. Prefer the smallest design that covers the case; delete rather than accumulate. No dead options, no speculative abstraction, no commented-out code.

- Every function is fully typed (mypy is strict); docstrings where the name is not enough.
- Errors say what to fix, naming the file, key and value.
- Every behaviour has a test; every keyword has an entry in `docs/` with its parameters and an example. An undocumented keyword is unfinished.
- The README's Layout and Commands stay in step with the repo.
