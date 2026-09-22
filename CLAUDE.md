# skilleval

Declarative, file-based tests for LLM setups — a harness, model, skills and config — and for single components such as one skill. Three kinds of test: `static-check` (reads a prompt as text, no model), `evaluation` (runs a setup against tasks) and `benchmark` (compares setups). Importable as a package; the CLI mirrors pytest.

## Layout

- `specs/` — the design specs. [specs/README.md](specs/README.md) is the entry point, [specs/static-checking.md](specs/static-checking.md) covers static checks, `specs/examples/` holds worked YAML. Read them before changing behaviour, and update them when a decision changes.
- `src/skilleval/` — the package. `tests/` — pytest suite. `docs/` — user-facing documentation.

## Bar

This is meant to be a professional tool, so the code has to read that way: concise, readable, high quality. Prefer the smallest design that covers the case; delete rather than accumulate. No dead options, no speculative abstraction, no commented-out code.

- Type hints on public functions, docstrings where the name is not enough.
- Errors say what to fix, naming the file, key and value.
- Every behaviour has a test; every keyword has an entry in `docs/` with its parameters and an example. An undocumented keyword is unfinished.
