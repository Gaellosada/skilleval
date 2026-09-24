# skilleval

Declarative, file-based tests for LLM setups (a harness, model, skills and config) and for single components such as one skill.

## Commands

```
pip install -e .[dev]   # the package, pytest, pytest-cov, ruff and mypy
pytest -q               # the suite
ruff check              # lint
mypy                    # type check
skilleval evals/        # run the tests in a directory
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
│   ├── evaluations.md       the evaluation kind (to be written)
│   ├── benchmarks.md        the benchmark kind (to be written)
│   └── examples/            worked test files
├── src/skilleval/           the package: CLI, collection, reporting
│   ├── testfile/            a test file (*.eval.yml) read into dataclasses
│   └── static/              the static-check kind: prompt extraction, lint, formats, constraints
├── tests/                   the suite: conventions in tests/README.md
│   ├── unit/                one directory per package, one file per module with behaviour
│   └── integration/         through collect, run or main
│       ├── runner/
│       ├── cli/
│       └── end_to_end/      one run over a frozen, realistic fixture project
└── docs/                    user documentation, one entry per keyword; README.md indexes them
    ├── test-file.md         root, tests, kind, prompt, needs, paths
    ├── templates.md         templates, uses, merging
    ├── checks.md            lint, format, constraints, detection
    └── cli.md               arguments, node ids, options, output, exit codes, Python API
```
