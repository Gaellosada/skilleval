# skilleval

Declarative, file-based tests for LLM setups (a harness, model, skills and config) and for single components such as one skill.

> **Anthropic only, for now.** Evaluations run on Claude Code, the one harness supported, as the user set it up or blank, and the formats a static check asserts are Anthropic's `SKILL.md`, subagent file and `CLAUDE.md`, and JSON. Written for Linux, WSL included; macOS is untested and Windows is not supported: see [docs/limits.md](docs/limits.md).

> **Python 3.12.2 or later.** skilleval deletes through `tempfile.TemporaryDirectory` the workspaces, the results and the copies `run` blocks check, so that a tree the model left read-only is deleted too. Before 3.12.2, that cleanup follows symbolic links when it resets the permissions of what it cannot delete ([CVE-2023-6597](https://nvd.nist.gov/vuln/detail/CVE-2023-6597)), so a link the model leaves in a read-only folder could have skilleval change the permissions of the file it points to. `pip` refuses to install on an older Python.

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
│   └── evaluation/          the evaluation kind: settings, workspace, expect, judge, and harness/, one module per backend
├── tests/                   the suite: conventions in tests/README.md
│   ├── unit/                one directory per package, one file per module with behaviour
│   └── integration/         through collect, run or main
│       ├── runner/
│       ├── cli/
│       ├── evaluation/      an evaluation run with a stand-in for the harness
│       ├── examples/        the worked examples of specs/examples load
│       └── end_to_end/      one run over a frozen, realistic fixture project
└── docs/                    user documentation, one entry per keyword; README.md indexes them
    ├── test-file.md         root, judge_defaults, tests, templates, kind, prompt, needs, uses, paths, globs
    ├── templates.md         templates, uses, merging
    ├── checks.md            lint, format, constraints, detection
    ├── evaluations.md       setup, model, task, expect, the judge, limits, the workspace, the results it keeps, skilleval's own suite
    ├── config.md            the settings file: backend, credentials
    ├── limits.md            what is not supported: platforms, harness blank, the judge, effort, usage, credentials, run, backends
    └── cli.md               arguments, node ids, options, output, exit codes, Python API
```
