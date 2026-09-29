# skilleval

Declarative, file-based tests for LLM setups (a harness, model, skills and config) and for single components such as one skill.

> **Anthropic only, for now.** Evaluations run on Claude Code, the one harness supported, and the formats a static check asserts are Anthropic's: `SKILL.md` and `CLAUDE.md`.

## Commands

```
pip install -e .[dev]   # the package, pytest, pytest-cov, ruff and mypy
pytest -q               # the suite: never runs Claude Code, see docs/evaluations.md
ruff check              # lint
mypy                    # type check
skilleval evals/        # run the tests in a directory
skilleval --static-checks evals/   # only the static checks; --evaluations for the others
```

CI runs `ruff check`, `mypy` and `pytest` with coverage on pushes to `main` and on pull requests, then sends the results to SonarQube Cloud ([.github/workflows/ci.yml](.github/workflows/ci.yml), [sonar-project.properties](sonar-project.properties)).

## Layout

```
.
├── specs/                   design specs: read them before changing behaviour
│   ├── README.md            entry point: goal, test file format, the three test kinds
│   ├── cli.md               CLI, discovery, node ids, exit codes
│   ├── templates.md         reusable test bodies and how they merge
│   ├── static-checking.md   static checks: lint, formats, constraints
│   ├── evaluations.md       the evaluation kind
│   ├── config.md            the settings file, .skilleval/config.yml
│   ├── benchmarks.md        the benchmark kind (to be written)
│   └── examples/            worked test files
├── src/skilleval/           the package: CLI, collection, reporting
│   ├── testfile/            a test file (*.eval.yml) read into dataclasses
│   ├── static/              the static-check kind: prompt extraction, lint, formats, constraints
│   └── evaluation/          the evaluation kind: settings, workspace, expect, and harness/, one module per backend
├── tests/                   the suite: conventions in tests/README.md
│   ├── unit/                one directory per package, one file per module with behaviour
│   └── integration/         through collect, run or main
│       ├── runner/
│       ├── cli/
│       ├── evaluation/      an evaluation run with a stand-in for the harness
│       ├── examples/        the worked examples of specs/examples load
│       └── end_to_end/      one run over a frozen, realistic fixture project
└── docs/                    user documentation, one entry per keyword; README.md indexes them
    ├── test-file.md         root, tests, templates, kind, prompt, needs, uses, paths, globs
    ├── templates.md         templates, uses, merging
    ├── checks.md            lint, format, constraints, detection
    ├── evaluations.md       setup, model, task, expect, limits, the workspace, the results it keeps, skilleval's own suite
    ├── config.md            the settings file: backend, credentials
    └── cli.md               arguments, node ids, options, output, exit codes, Python API
```
