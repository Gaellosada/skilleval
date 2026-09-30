# skilleval documentation

skilleval runs declarative tests, written in YAML test files, against an LLM setup and its prompts, such as skills and `CLAUDE.md` files. There are two kinds of test: `static-check` reads a prompt as text and checks it without running a model; `evaluation` runs a setup on a task and checks the reply and the files it leaves.

- [test-file.md](test-file.md) — the test file: `root`, `judge_defaults`, `tests`, `kind`, `prompt`, `needs`, how paths resolve, and the glob syntax.
- [templates.md](templates.md) — `templates` and `uses`: reusable test bodies and how they merge.
- [checks.md](checks.md) — `lint`, `format` and `constraints`, their parameters, and how paths, URLs and code blocks are detected.
- [evaluations.md](evaluations.md) — `setup`, `model`, `task`, `expect` and the limits of an evaluation, the judge and `judge_defaults`, its workspace, the results it keeps, what it reports, and what skilleval's own suite leaves untested in it.
- [config.md](config.md) — `.skilleval/config.yml`, the settings of whoever runs the tests: `backend` and the credentials.
- [limits.md](limits.md) — what is not supported and what a run cannot keep out: platforms, `harness: blank`, `judge`, `effort`, credentials, `run`, backends.
- [cli.md](cli.md) — the `skilleval` command: arguments, node ids, options, output, exit codes and the Python API.

## Keywords

- Test file: [`root`](test-file.md#root), [`judge_defaults`](evaluations.md#judge_defaults), [`tests`](test-file.md#tests), [`templates`](templates.md#templates).
- Test: [`kind`](test-file.md#kind), [`prompt`](test-file.md#prompt), [`needs`](test-file.md#needs), [`uses`](templates.md#uses), [`lint`](checks.md#lint), [`format`](checks.md#format), [`constraints`](checks.md#constraints).
- Evaluation: [`setup`](evaluations.md#setup), [`model`](evaluations.md#model), [`task`](evaluations.md#task), [`expect`](evaluations.md#expect), [`max_tokens`](evaluations.md#max_tokens), [`max_budget_usd`](evaluations.md#max_budget_usd).
- Setup: [`harness`](evaluations.md#harness), [`permissions`](evaluations.md#permissions), [`effort`](evaluations.md#effort), [`override_system_prompt`](evaluations.md#override_system_prompt), [`append_system_prompt`](evaluations.md#append_system_prompt), [`skills`](evaluations.md#skills), [`working_folder`](evaluations.md#working_folder).
- Settings: [`backend`](config.md#backend), [`ANTHROPIC_API_KEY`](config.md#anthropic_api_key), [`CLAUDE_CODE_OAUTH_TOKEN`](config.md#claude_code_oauth_token).
- Expect: [`response`](evaluations.md#response), [`file`](evaluations.md#file), [`with_path`](evaluations.md#with_path), [`run`](evaluations.md#run), [`timeout`](evaluations.md#timeout), [`judge`](evaluations.md#judge), [`require`](evaluations.md#require), [`files`](evaluations.md#files), [`can_see_task`](evaluations.md#can_see_task), [`can_see_response`](evaluations.md#can_see_response), [`severity`](evaluations.md#severity).
- Judge, in [`judge_defaults`](evaluations.md#judge_defaults) or beside `judge`: `model`, `effort`, `harness`, `max_tokens`, `max_budget_usd`.
- Prompt: [`file`](test-file.md#file), [`include`](test-file.md#include), [`exclude`](test-file.md#exclude).
- Any check: [`severity`](checks.md#severity).
- Lint: [`chars`](checks.md#chars), [`markdown_links`](checks.md#markdown_links), [`paths_exist`](checks.md#paths_exist).
- Format: [`anthropic-skill`](checks.md#anthropic-skill), [`anthropic-agent`](checks.md#anthropic-agent), [`anthropic-claude`](checks.md#anthropic-claude).
- Constraints: [`words`](checks.md#words), [`lines`](checks.md#lines), [`contains`](checks.md#contains), [`contains_any`](checks.md#contains_any), [`contains_none`](checks.md#contains_none), [`matches`](checks.md#matches), [`matches_any`](checks.md#matches_any), [`matches_none`](checks.md#matches_none), [`paths`](checks.md#paths), [`urls`](checks.md#urls), [`code`](checks.md#code).
- Constraint parameters: [`min`, `max`](checks.md#bounds), [`count`](checks.md#bounds), [`occurrences`](checks.md#occurrences), [`words`, `patterns`](checks.md#words-and-patterns-lists), [`case_sensitive`](checks.md#case_sensitive), `except`, `default` and `style` under [`paths`](checks.md#paths), [`urls`](checks.md#urls) and [`code`](checks.md#code).
- Command line: [`-k`](cli.md#-k), [`-x`](cli.md#-x), [`-q`](cli.md#-q), [`-v`](cli.md#-v), [`--static-checks`](cli.md#--static-checks), [`--evaluations`](cli.md#--evaluations), [`--collect-only`](cli.md#--collect-only), [`--version`](cli.md#--version), [`-h`](cli.md#-h).
