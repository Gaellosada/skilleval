"""How `load` turns the keys of an evaluation into `Test.evaluation`: the keys as written, then
the templates merged in. Specified in specs/evaluations.md and specs/templates.md. The static-check
keys an evaluation refuses are rows of test_load.py."""

import textwrap
from pathlib import Path

import pytest
from conftest import FILE, Project

from skilleval.testfile import (
    Check,
    Evaluation,
    Expectation,
    FilePrompt,
    Judge,
    LoadError,
    Run,
    Setup,
    Task,
    TextPrompt,
    load,
)

TEMPLATES = "shared.eval.yml"
USES = f"{TEMPLATES}#a"
QUESTION = "Is every statement in the reply true?"
CONSTRAINTS = {  # one entry per constraint, as the keys of a `file` block
    "words": "{min: 100, max: 600}",
    "lines": "{max: 200}",
    "contains": "[qubit, superposition]",
    "contains_any": "{words: [fast, quick], case_sensitive: true}",
    "contains_none": "I cannot",
    "matches": "{patterns: ['^def slugify'], occurrences: 1}",
    "matches_any": "{patterns: ['(?i)entangle']}",
    "matches_none": "{patterns: ['TODO']}",
    "paths": "{style: posix}",
    "urls": "{default: deny, except: [github.com]}",
    "code": "{count: {max: 0}, severity: warn}",
}


def contains(word: str, severity: str | None = None) -> Check:
    return Check("contains", {"words": [word], "occurrences": {"min": 1, "max": None}, "case_sensitive": False}, severity)


def bare(**keys: str | None) -> str:
    """The lines of the smallest evaluation, with `keys` written over them; None removes one."""
    body = {"model": "claude-sonnet-5", "task": "Explain this repository.", "setup": "{harness: user_local}"} | keys
    return "".join(f"{key}: {value}\n" for key, value in body.items() if value is not None)


def evaluation(project: Project, body: str, templates: str = "") -> Evaluation:
    """Write `FILE`, whose evaluation `t` holds the lines of `body`, and the
    `templates:` entries in `shared.eval.yml` at the root; load and return the evaluation."""
    project.write(TEMPLATES, "root: pyproject.toml\ntemplates:\n" + textwrap.indent(templates, "  "))
    project.tests("t:\n  kind: evaluation\n" + textwrap.indent(textwrap.dedent(body), "  "))
    loaded = project.load(FILE).tests["t"].evaluation
    assert loaded is not None
    return loaded


def load_error(project: Project, body: str, templates: str = "") -> LoadError:
    with pytest.raises(LoadError) as info:
        evaluation(project, body, templates)
    return info.value


def summary(loaded: Evaluation) -> list[tuple[str, dict[str, list[str]]]]:
    """Each task with the names of its checks, by what they check."""
    return [(t.text, {e.with_path or "response": [c.name for c in e.checks] for e in t.expect}) for t in loaded.tasks]


# The keys as written


def test_spec_example_loads_to_the_exact_evaluation(project: Project) -> None:
    project.write("evals/fixtures/refactor/utils.py")
    loaded = evaluation(project, """
        setup:
          harness: user_local
          permissions: bypass
          effort: medium
          override_system_prompt:
            file: prompts/reviewer.md
          working_folder: ./fixtures/refactor
        model: claude-opus-5-5
        task: Split utils.py into one module per concern.
        expect:
          - response:
              - contains: utils
          - file:
              with_path: utils/strings.py
        max_tokens: 200000
        max_budget_usd: 5
    """)
    setup = Setup("user_local", "bypass", "medium", FilePrompt(project.root / "prompts/reviewer.md"),
                  working_folder=project.root / "evals/fixtures/refactor")
    expect = (Expectation(None, (contains("utils"),)), Expectation("utils/strings.py"))
    task = Task("Split utils.py into one module per concern.", expect)
    assert loaded == Evaluation(setup, "claude-opus-5-5", (task,), 200000, 5)


def test_optional_keys_default_and_the_test_keeps_its_needs(project: Project) -> None:
    project.tests("gate: {kind: static-check, prompt: hi}\nt:\n  kind: evaluation\n  needs: gate\n"
                  + textwrap.indent(bare(max_budget_usd="0.5"), "  "))
    test = project.load("evals/a.eval.yml").tests["t"]
    assert (test.kind, test.needs, test.prompt, test.checks) == ("evaluation", ("gate",), None, ())
    assert test.evaluation == Evaluation(
        Setup("user_local", effort="high"), "claude-sonnet-5", (Task("Explain this repository."),), max_budget_usd=0.5
    )


def test_setup_holds_inline_prompts_and_paths_resolved_from_the_test_file_or_the_root(project: Project) -> None:
    for path in ("skills/refactor/SKILL.md", "evals/skills/deploy/SKILL.md", "evals/fixtures/pr/pr.diff"):
        project.write(path)
    listed = evaluation(project, bare(setup=None) + textwrap.dedent("""
        setup:
          harness: user_local
          append_system_prompt: {file: ./fr.md}
          skills: [skills/refactor, ./skills/deploy]
          working_folder: ./fixtures/pr
    """)).setup
    assert listed == Setup(
        "user_local", append_system_prompt=FilePrompt(project.root / "evals/fr.md"),
        skills=(project.root / "skills/refactor", project.root / "evals/skills/deploy"),
        working_folder=project.root / "evals/fixtures/pr",
    )
    single = "{harness: blank, override_system_prompt: Be brief., skills: skills/refactor}"
    assert evaluation(project, bare(setup=single)).setup == Setup(
        "blank", override_system_prompt=TextPrompt("Be brief."), skills=(project.root / "skills/refactor",)
    )


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_effort_is_one_of_five_levels(project: Project, effort: str) -> None:
    assert evaluation(project, bare(setup=f"{{harness: user_local, effort: {effort}}}")).setup.effort == effort


@pytest.mark.parametrize("body, key, offending", [
    (bare(task=None), "tests.t.task", "task"),
    (bare(task="{file: task.md}"), "tests.t.task", "task.md"),
    (bare(task="'  '"), "tests.t.task", "'  '"),
    (bare(model=None), "tests.t.model", "model"),
    (bare(model="[claude-sonnet-5, claude-opus-5-5]"), "tests.t.model", "claude-opus-5-5"),
    (bare(model="'  '"), "tests.t.model", "'  '"),
    (bare(max_tokens="0"), "tests.t.max_tokens", "0"),
    (bare(max_tokens="1.5"), "tests.t.max_tokens", "1.5"),
    (bare(max_tokens="true"), "tests.t.max_tokens", "integer, not True"),
    (bare(max_budget_usd="0"), "tests.t.max_budget_usd", "0"),
    (bare(max_budget_usd="-1"), "tests.t.max_budget_usd", "-1"),
    (bare(max_budget_usd="1" + "0" * 400), "tests.t.max_budget_usd", "1000"),
    (bare(max_budget_usd="cheap"), "tests.t.max_budget_usd", "cheap"),
    (bare(max_budget_usd="true"), "tests.t.max_budget_usd", "True"),
    (bare(max_budget_usd=".inf"), "tests.t.max_budget_usd", "inf"),
    (bare(max_budget_usd=".nan"), "tests.t.max_budget_usd", "nan"),
], ids=["no task", "task as a file", "blank task", "no model", "two models", "blank model", "zero tokens",
        "fractional tokens", "boolean tokens", "no budget", "negative budget", "budget beyond any number", "budget in words", "boolean budget", "endless budget",
        "budget that is no number"])
def test_task_model_or_limit_missing_or_of_another_shape_is_a_load_error(
    project: Project, body: str, key: str, offending: str
) -> None:
    e = load_error(project, body)
    assert (e.path, e.key) == (project.root / FILE, key)
    assert offending in e.message


def test_a_project_below_a_skilleval_folder_loads_its_skills_and_working_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = Project(tmp_path / ".skilleval/project", capsys)  # a folder of that name the project lives in, not one of its own
    for path in ("pyproject.toml", "skills/refactor/SKILL.md", "evals/fixtures/pr/pr.diff"):
        project.write(path)
    setup = evaluation(project, bare(setup="{harness: user_local, skills: skills/refactor, working_folder: ./fixtures/pr}")).setup
    assert setup == Setup("user_local", skills=(project.root / "skills/refactor",), working_folder=project.root / "evals/fixtures/pr")


@pytest.mark.parametrize("setup, key, offending", [
    ("user_local", "", "user_local"),
    ("{}", ".harness", "harness"),
    ("{harness: claude}", ".harness", "claude"),
    ("{harness: user_local, permissions: sometimes}", ".permissions", "sometimes"),
    ("{harness: user_local, effort: extreme}", ".effort", "extreme"),
    ("{harness: user_local, effort: High}", ".effort", "High"),
    ("{harness: user_local, override_system_prompt: A, append_system_prompt: B}", "", "append_system_prompt"),
    ("{harness: user_local, override_system_prompt: {include: '*.md'}}", ".override_system_prompt", "include"),
    ("{harness: user_local, skills: 3}", ".skills", "3"),
    ("{harness: user_local, skills: ''}", ".skills", "''"),
    ("{harness: user_local, skills: skills/missing}", ".skills", "skills/missing"),
    ("{harness: user_local, skills: [skills/ok, skills/empty]}", ".skills[1]", "SKILL.md"),
    ("{harness: user_local, skills: [skills/ok/SKILL.md]}", ".skills[0]", "skills/ok/SKILL.md"),
    ("{harness: user_local, skills: [skills/ok, .skilleval/skills/tidy]}", ".skills[1]", ".skilleval/skills/tidy"),
    ("{harness: user_local, working_folder: 3}", ".working_folder", "3"),
    ("{harness: user_local, working_folder: nowhere}", ".working_folder", "nowhere"),
    ("{harness: user_local, working_folder: ./}", ".working_folder", "holds this file"),
    ("{harness: user_local, working_folder: evals/..}", ".working_folder", "holds this file"),
    ("{harness: user_local, working_folder: skills/ok/SKILL.md}", ".working_folder", "skills/ok/SKILL.md"),
    ("{harness: user_local, working_folder: .skilleval}", ".working_folder", ".skilleval"),
    ("{harness: user_local, working_folder: .skilleval/results}", ".working_folder", ".skilleval/results"),
    ("{harness: user_local, working_folder: fixtures/../.skilleval}", ".working_folder", "fixtures/../.skilleval"),
    ("{harness: user_local, mcp_servers: {}}", ".mcp_servers", "mcp_servers"),
], ids=["not a mapping", "no harness", "unknown harness", "unknown permissions", "unknown effort", "effort High, as written",
        "both system prompts", "system prompt as an include", "skills as a number", "skill with no path",
        "skill that does not exist",
        "skill without a SKILL.md", "skill that is a file", "skill in a .skilleval folder", "working folder as a number",
        "working folder that does not exist", "working folder of the test file", "working folder above the test file",
        "working folder that is a file", "working folder that is a .skilleval folder", "working folder in one",
        "working folder naming one through a detour", "unknown key"])
def test_bad_setup_is_a_load_error_at_its_key(project: Project, setup: str, key: str, offending: str) -> None:
    project.write("skills/ok/SKILL.md")
    project.write("skills/empty/notes.md")
    project.write(".skilleval/results/evals/a.eval.yml/t/conversation.jsonl", "{}\n")
    project.write(".skilleval/skills/tidy/SKILL.md")
    e = load_error(project, bare(setup=setup))
    assert e.key == "tests.t.setup" + key
    assert offending in e.message


# Expect


def test_response_and_file_checks_read_as_the_constraints_of_a_static_check(project: Project) -> None:
    entries = ", ".join(f"{{{name}: {params}}}" for name, params in CONSTRAINTS.items())
    keys = ", ".join(f"{name}: {params}" for name, params in CONSTRAINTS.items())
    project.tests(f"s: {{kind: static-check, prompt: hi, constraints: [{entries}]}}")
    constraints = project.load("evals/a.eval.yml").tests["s"].checks
    expect = f"[{{response: [{entries}]}}, {{file: {{with_path: docs/module layout.md, {keys}}}}}]"
    (task,) = evaluation(project, bare(expect=expect)).tasks
    assert len(constraints) == len(CONSTRAINTS)
    assert task.expect == (Expectation(None, constraints), Expectation("docs/module layout.md", constraints))


def test_blocks_on_the_same_thing_join_in_order_of_first_appearance_each_with_its_severity(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - response: [{contains: a}]
          - file: {with_path: x.md, words: {max: 5}, severity: error}
          - file: {with_path: docs/../x.md, words: {max: 3}, severity: warn}
          - response: [{contains: b}]
            severity: warn
          - file: {with_path: "*.md", severity: warn}
          - file: {with_path: "*.md", severity: warn}
          - file: {with_path: y.md}
          - file: {with_path: y.md/, severity: warn}
    """)).tasks
    assert task.expect == (
        Expectation(None, (contains("a"), contains("b", "warn"))),
        Expectation("x.md", (Check("words", {"min": None, "max": 5}, "error"), Check("words", {"min": None, "max": 3}, "warn"))),
        Expectation("*.md", (), "warn"),
        Expectation("y.md"),
    )


def test_severity_of_a_block_covers_its_checks_unless_they_write_their_own(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - response:
              - contains: [qubit]
              - words:
                  max: 400
                  severity: error
            severity: warn
          - file:
              with_path: NOTES.md
              severity: warn
              lines:
                max: 50
    """)).tasks
    assert task.expect == (
        Expectation(None, (contains("qubit", "warn"), Check("words", {"min": None, "max": 400}, "error"))),
        Expectation("NOTES.md", (Check("lines", {"min": None, "max": 50}, "warn"),), "warn"),
    )


@pytest.mark.parametrize("expect, key, offending", [
    ("{response: []}", "", "response"),
    ("[response]", "[0]", "response"),
    ("[{severity: warn}]", "[0]", "severity"),
    ("[{response: [], file: {with_path: a.md}}]", "[0]", "file"),
    ("[{reply: []}]", "[0].reply", "reply"),
    ("[{response: [], severity: fatal}]", "[0].severity", "fatal"),
    ("[{response: [], severity: false}]", "[0].severity", "False"),
    ("[{file: {with_path: a.md}, severity: warn}]", "[0].severity", "beside with_path"),
    ("[{response: {contains: a}}]", "[0].response", "contains"),
    ("[{response: [chars]}]", "[0].response[0]", "chars"),
    ("[{response: [{words: {max: many}}]}]", "[0].response[0].words.max", "many"),
    ("[{file: {words: {max: 5}}}]", "[0].file.with_path", "with_path is required"),
    ("[{file: {with_path: }}]", "[0].file.with_path", "None"),
    ("[{file: {with_path: ''}}]", "[0].file.with_path", "''"),
    ("[{file: {with_path: docs/..}}]", "[0].file.with_path", "docs/.."),
    ("[{file: {with_path: a.md, paths: }}]", "[0].file.paths", "{}"),
    ("[{file: {with_path: ./a.md}}]", "[0].file.with_path", "./a.md"),
    ("[{file: {with_path: /tmp/a.md}}]", "[0].file.with_path", "/tmp/a.md"),
    ("[{file: {with_path: docs/../../a.md}}]", "[0].file.with_path", "docs/../../a.md"),
    ("[{file: {with_path: a.md, severity: fatal}}]", "[0].file.severity", "fatal"),
    ("[{file: {with_path: a.md, lint: [chars]}}]", "[0].file.lint", "lint"),
    ("[{file: {with_path: a.md, chars: {}}}]", "[0].file.chars", "chars"),
    ("[{file: {with_path: a.md, words: {max: many}}}]", "[0].file.words.max", "many"),
], ids=["not a list", "block that is not a mapping", "block checking nothing", "block checking two things",
        "unknown block", "bad severity beside response", "boolean severity", "severity beside file", "response that is not a list",
        "lint under response", "bad parameter under response", "file without with_path", "with_path left empty", "empty with_path", "with_path of the workspace itself",
        "check left empty in file",
        "with_path from the test file",
        "absolute with_path", "with_path climbing out", "bad severity in file", "lint in file", "lint check in file",
        "bad parameter in file"])
def test_bad_expect_is_a_load_error_at_its_key(project: Project, expect: str, key: str, offending: str) -> None:
    e = load_error(project, bare(expect=expect))
    assert e.key == "tests.t.expect" + key
    assert offending in e.message


def test_a_run_block_loads_with_the_directory_of_its_file_a_timeout_of_600_unless_set_and_its_severity(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - run: python -m pytest -q
          - run: |
              make build
              make test
            timeout: 30
            severity: warn
          - run: ruff check
            timeout: 0.5
            severity: error
    """)).tasks
    evals = project.root / "evals"
    assert task.expect == (
        Run("python -m pytest -q", evals, 600),
        Run("make build\nmake test\n", evals, 30, "warn"),
        Run("ruff check", evals, 0.5, "error"),
    )


def test_run_blocks_keep_their_place_among_the_others_and_never_join(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - run: pytest
          - response: [{contains: a}]
          - run: pytest
          - file: {with_path: x.md}
          - response: [{contains: b}]
          - run: pytest
            severity: warn
    """)).tasks
    evals = project.root / "evals"
    assert task.expect == (
        Run("pytest", evals),
        Expectation(None, (contains("a"), contains("b"))),
        Run("pytest", evals),
        Expectation("x.md"),
        Run("pytest", evals, severity="warn"),
    )


@pytest.mark.parametrize("expect, key, offending", [
    ("[{run: }]", "[0].run", "None"),
    ("[{run: ''}]", "[0].run", "''"),
    ("[{run: '  '}]", "[0].run", "'  '"),
    ("[{run: 3}]", "[0].run", "3"),
    ("[{run: [pytest, ruff]}]", "[0].run", "ruff"),
    ("[{run: pytest, timeout: 0}]", "[0].timeout", "0"),
    ("[{run: pytest, timeout: -5}]", "[0].timeout", "-5"),
    ("[{run: pytest, timeout: soon}]", "[0].timeout", "soon"),
    ("[{run: pytest, timeout: true}]", "[0].timeout", "True"),
    ("[{run: pytest, severity: fatal}]", "[0].severity", "fatal"),
    ("[{run: pytest, retries: 2}]", "[0].retries", "retries"),
    ("[{run: pytest, with_path: a.md}]", "[0].with_path", "with_path"),
    ("[{response: [], run: pytest}]", "[0]", "run"),
    ("[{file: {with_path: a.md}, run: pytest}]", "[0]", "run"),
    ("[{file: {with_path: a.md, timeout: 5}}]", "[0].file.timeout", "timeout"),
    ("[{response: [], timeout: 5}]", "[0].timeout", "timeout"),
    ("[{file: {with_path: a.md}, timeout: 5}]", "[0].timeout", "timeout"),
], ids=["no command", "empty command", "blank command", "command as a number", "command as a list",
        "zero timeout", "negative timeout", "timeout in words", "boolean timeout", "bad severity beside run",
        "unknown key beside run", "with_path beside run", "run beside response", "run beside file", "timeout in file",
        "timeout beside response", "timeout beside file"])
def test_bad_run_block_is_a_load_error_at_its_key(project: Project, expect: str, key: str, offending: str) -> None:
    e = load_error(project, bare(expect=expect))
    assert (e.path, e.key) == (project.root / FILE, "tests.t.expect" + key)
    assert offending in e.message


def test_a_run_block_of_a_file_loaded_by_a_relative_path_names_its_directory_absolute(project: Project) -> None:
    project.tests("t:\n  kind: evaluation\n" + textwrap.indent(bare(expect="[{run: pytest}]"), "  "))
    loaded = load(Path(FILE)).tests["t"].evaluation
    assert loaded is not None
    assert loaded.tasks[0].expect == (Run("pytest", project.root / "evals"),)


def test_a_judge_block_loads_with_its_question_the_answer_required_and_the_documented_defaults_unless_set(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - judge: Is every statement in the reply true?
            require: YES
          - judge: |
              Does the reply
              name its sources?
            require: "NO"
            files: [docs/../NOTES.md, src/a.py]
            can_see_task: false
            can_see_response: false
            model: claude-opus-5-5
            effort: low
            harness: blank
            max_tokens: 5000
            max_budget_usd: 0.5
            severity: warn
          - judge: Is NOTES.md a list?
            require: YES
            files: NOTES.md
            can_see_task: true
          - judge: Is it short?
            require: YES
            files: []
    """)).tasks
    assert task.expect == (
        Judge(QUESTION, "YES", (), True, True, "claude-sonnet-5-5", "high", None, 100000, 1, None),
        Judge("Does the reply\nname its sources?\n", "NO", ("NOTES.md", "src/a.py"), False, False,
              "claude-opus-5-5", "low", "blank", 5000, 0.5, "warn"),
        Judge("Is NOTES.md a list?", "YES", ("NOTES.md",)),
        Judge("Is it short?", "YES"),
    )


@pytest.mark.parametrize("written, answer", [
    ("YES", "YES"), ("yes", "YES"), ("true", "YES"), ("on", "YES"), ('"YES"', "YES"),
    ("NO", "NO"), ("no", "NO"), ("false", "NO"), ("off", "NO"), ("'NO'", "NO"),
])
def test_require_is_yes_or_no_as_that_text_or_as_the_boolean_yaml_reads_however_spelled(
    project: Project, written: str, answer: str
) -> None:
    (task,) = evaluation(project, bare(expect=f"[{{judge: '{QUESTION}', require: {written}}}]")).tasks
    assert task.expect == (Judge(QUESTION, answer),)


def test_judge_blocks_keep_their_place_among_the_others_and_never_join(project: Project) -> None:
    (task,) = evaluation(project, bare() + textwrap.dedent("""
        expect:
          - judge: Is it right?
            require: YES
          - response: [{contains: a}]
          - judge: Is it right?
            require: YES
          - run: pytest
          - response: [{contains: b}]
          - judge: Is it right?
            require: NO
    """)).tasks
    assert task.expect == (
        Judge("Is it right?", "YES"),
        Expectation(None, (contains("a"), contains("b"))),
        Judge("Is it right?", "YES"),
        Run("pytest", project.root / "evals"),
        Judge("Is it right?", "NO"),
    )


@pytest.mark.parametrize("expect, key, offending", [
    ("[{judge: , require: YES}]", "[0].judge", "None"),
    ("[{judge: '  ', require: YES}]", "[0].judge", "'  '"),
    ("[{judge: 3, require: YES}]", "[0].judge", "3"),
    ("[{judge: {file: question.md}, require: YES}]", "[0].judge", "question.md"),
    ("[{judge: 'Right?'}]", "[0].require", "require is required, YES or NO"),
    ("[{judge: 'Right?', require: }]", "[0].require", "None"),
    ("[{judge: 'Right?', require: maybe}]", "[0].require", "'maybe'"),
    ("[{judge: 'Right?', require: 'yes'}]", "[0].require", "'yes'"),
    ("[{judge: 'Right?', require: UNKNOWN}]", "[0].require", "'UNKNOWN'"),
    ("[{judge: 'Right?', require: 1}]", "[0].require", "1"),
    ("[{judge: 'Right?', require: [YES]}]", "[0].require", "[True]"),
    ("[{judge: 'Right?', require: YES, files: 3}]", "[0].files", "3"),
    ("[{judge: 'Right?', require: YES, files: ./a.md}]", "[0].files", "./a.md"),
    ("[{judge: 'Right?', require: YES, files: [a.md, /etc/passwd]}]", "[0].files[1]", "/etc/passwd"),
    ("[{judge: 'Right?', require: YES, files: [../a.md]}]", "[0].files[0]", "../a.md"),
    ("[{judge: 'Right?', require: YES, files: ['']}]", "[0].files[0]", "''"),
    ("[{judge: 'Right?', require: YES, can_see_task: 'no'}]", "[0].can_see_task", "'no'"),
    ("[{judge: 'Right?', require: YES, can_see_response: 0}]", "[0].can_see_response", "0"),
    ("[{judge: 'Right?', require: YES, model: ''}]", "[0].model", "''"),
    ("[{judge: 'Right?', require: YES, effort: huge}]", "[0].effort", "huge"),
    ("[{judge: 'Right?', require: YES, harness: docker}]", "[0].harness", "docker"),
    ("[{judge: 'Right?', require: YES, max_tokens: 0}]", "[0].max_tokens", "0"),
    ("[{judge: 'Right?', require: YES, max_tokens: 1.5}]", "[0].max_tokens", "1.5"),
    ("[{judge: 'Right?', require: YES, max_budget_usd: -1}]", "[0].max_budget_usd", "-1"),
    ("[{judge: 'Right?', require: YES, severity: fatal}]", "[0].severity", "fatal"),
    ("[{judge: 'Right?', require: YES, timeout: 5}]", "[0].timeout", "timeout"),
    ("[{judge: 'Right?', require: YES, with_path: a.md}]", "[0].with_path", "with_path"),
    ("[{judge: 'Right?', require: YES, permissions: bypass}]", "[0].permissions", "permissions"),
    ("[{judge: 'Right?', require: YES, run: pytest}]", "[0]", "judge"),
    ("[{judge: 'Right?', require: YES, response: []}]", "[0]", "judge"),
    ("[{run: pytest, require: YES}]", "[0].require", "require"),
    ("[{response: [], can_see_task: false}]", "[0].can_see_task", "can_see_task"),
    ("[{file: {with_path: a.md, files: [b.md]}}]", "[0].file.files", "files"),
], ids=["no question", "blank question", "question as a number", "question from a file", "no require", "empty require",
        "another answer", "yes in lower case as text", "the judge's own answer", "require as a number", "require as a list",
        "files as a number", "a file from the test file", "an absolute file", "a file climbing out", "an empty path",
        "can_see_task as text", "can_see_response as a number", "empty model", "unknown effort", "unknown harness",
        "zero max_tokens", "fractional max_tokens", "negative max_budget_usd", "bad severity beside judge",
        "timeout beside judge", "with_path beside judge", "a key of setup beside judge", "judge beside run",
        "judge beside response", "require beside run", "can_see_task beside response", "files in file"])
def test_bad_judge_block_is_a_load_error_at_its_key(project: Project, expect: str, key: str, offending: str) -> None:
    e = load_error(project, bare(expect=expect))
    assert (e.path, e.key) == (project.root / FILE, "tests.t.expect" + key)
    assert offending in e.message


def with_defaults(project: Project, defaults: str, **keys: str | None) -> Evaluation:
    """As `evaluation`, the top level of the file holding the lines of `defaults` too."""
    head = defaults + "root: pyproject.toml\ntests:\n  t:\n    kind: evaluation\n"
    loaded = load(project.write(FILE, head + textwrap.indent(bare(**keys), "    "))).tests["t"].evaluation
    assert loaded is not None
    return loaded


def test_judge_defaults_set_the_judge_of_every_block_of_the_file_and_a_block_wins_key_by_key(project: Project) -> None:
    defaults = "judge_defaults: {model: claude-opus-5-5, effort: low, harness: blank, max_tokens: 5000, max_budget_usd: 0.5}\n"
    (task,) = with_defaults(project, defaults, expect="""
      - {judge: 'A?', require: YES}
      - {judge: 'B?', require: YES, model: claude-haiku-4-5, harness: user_local, max_budget_usd: 2}
      - {judge: 'C?', require: YES, effort: max, max_tokens: 9}
    """).tasks
    assert task.expect == (
        Judge("A?", "YES", (), True, True, "claude-opus-5-5", "low", "blank", 5000, 0.5),
        Judge("B?", "YES", (), True, True, "claude-haiku-4-5", "low", "user_local", 5000, 2),
        Judge("C?", "YES", (), True, True, "claude-opus-5-5", "max", "blank", 9, 0.5),
    )


@pytest.mark.parametrize("defaults, expected", [
    ("{}", Judge("A?", "YES")),
    ("{effort: xhigh}", Judge("A?", "YES", effort="xhigh")),
    ("{max_budget_usd: 3}", Judge("A?", "YES", max_budget_usd=3)),
], ids=["an empty one sets nothing", "one key", "another"])
def test_a_key_judge_defaults_does_not_set_keeps_its_default(project: Project, defaults: str, expected: Judge) -> None:
    (task,) = with_defaults(project, f"judge_defaults: {defaults}\n", expect="[{judge: 'A?', require: YES}]").tasks
    assert task.expect == (expected,)


@pytest.mark.parametrize("defaults, key, offending", [
    ("judge_defaults:\n", "judge_defaults", "None"),
    ("judge_defaults: claude-opus-5-5\n", "judge_defaults", "claude-opus-5-5"),
    ("judge_defaults: [model]\n", "judge_defaults", "model"),
    ("judge_defaults: {model: ''}\n", "judge_defaults.model", "''"),
    ("judge_defaults: {effort: huge}\n", "judge_defaults.effort", "huge"),
    ("judge_defaults: {harness: docker}\n", "judge_defaults.harness", "docker"),
    ("judge_defaults: {max_tokens: many}\n", "judge_defaults.max_tokens", "many"),
    ("judge_defaults: {max_budget_usd: 0}\n", "judge_defaults.max_budget_usd", "0"),
    ("judge_defaults: {can_see_task: false}\n", "judge_defaults.can_see_task", "can_see_task"),
    ("judge_defaults: {require: YES}\n", "judge_defaults.require", "require"),
    ("judge_defaults: {severity: warn}\n", "judge_defaults.severity", "severity"),
    ("judge_defaults: {effort: low}\njudge_defaults: {model: claude-opus-5-5}\n", "judge_defaults", "repeated"),
], ids=["nothing", "text", "a list", "empty model", "unknown effort", "unknown harness", "max_tokens in words",
        "zero max_budget_usd", "a key of a block", "require", "severity", "written twice"])
def test_bad_judge_defaults_is_a_load_error_at_its_key_in_a_file_with_no_judge_block_too(
    project: Project, defaults: str, key: str, offending: str
) -> None:
    with pytest.raises(LoadError) as info:
        with_defaults(project, defaults)
    assert (info.value.path, info.value.key) == (project.root / FILE, key)
    assert offending in info.value.message


def test_judge_defaults_alone_make_no_test_file(project: Project) -> None:
    with pytest.raises(LoadError) as info:
        load(project.write(FILE, "judge_defaults: {effort: low}\n"))
    assert "neither" in info.value.message


# Templates


def test_the_nearest_value_wins_key_by_key_and_a_path_of_a_template_starts_at_its_file(project: Project) -> None:
    for path in ("skills/a/SKILL.md", "skills/b/SKILL.md", "one/x", "two/x"):
        project.write(path)
    own = bare(uses=f"[{USES}, {TEMPLATES}#b]", setup="{skills: skills/b, working_folder: two}", max_budget_usd="2")
    loaded = evaluation(project, own, textwrap.dedent("""
        a:
          kind: evaluation
          model: claude-opus-5-5
          max_tokens: 1000
          max_budget_usd: 1
          setup:
            harness: user_local
            permissions: bypass
            effort: low
            override_system_prompt: {file: ./prompts/reviewer.md}
            skills: [skills/a, skills/b]
            working_folder: one
        b:
          kind: evaluation
          model: claude-haiku-4-5
          max_tokens: 2000
    """))
    setup = Setup("user_local", "bypass", "low", FilePrompt(project.root / "prompts/reviewer.md"),
                  skills=(project.root / "skills/b",), working_folder=project.root / "two")
    assert loaded == Evaluation(setup, "claude-sonnet-5", (Task("Explain this repository."),), 2000, 2)


@pytest.mark.parametrize("templates, body, expected", [
    ("a: {kind: evaluation, task: A}\nb: {kind: evaluation, task: B}\n",
     bare(task="C", uses=f"[{TEMPLATES}#b, {USES}]"), [("B", {}), ("A", {}), ("C", {})]),
    ("a: {kind: evaluation, task: A}\n", bare(task=None, uses=USES), [("A", {})]),
    ("a: {kind: evaluation, task: A, expect: [{response: [{words: {max: 9}}]}]}\n",
     bare(task="C", uses=USES, expect="[{response: [{lines: {max: 9}}]}]"),
     [("A", {"response": ["words"]}), ("C", {"response": ["lines"]})]),
    ("z: {kind: evaluation, task: Z}\na: {kind: evaluation, task: A}\n"
     "b: {kind: evaluation, expect: [{file: {with_path: x.md, lines: {max: 9}}}]}\n",
     bare(task="C", uses=f"[{TEMPLATES}#z, {USES}, {TEMPLATES}#b]"), [("Z", {}), ("A", {"x.md": ["lines"]}), ("C", {})]),
    ("a: {kind: evaluation, task: A, expect: [{response: [{words: {max: 9}}]}, {file: {with_path: x.md}}]}\n",
     bare(task=None, uses=USES, expect="[{response: [{lines: {max: 9}}]}, {file: {with_path: y.md, code: {count: {max: 0}}}}]"),
     [("A", {"response": ["words", "lines"], "x.md": [], "y.md": ["code"]})]),
], ids=["the templates' tasks first, in uses order", "a template's task alone", "each expect on the task beside it",
        "an expect with no task beside it on the nearest above", "the test's expect joins the template's on its task"])
def test_tasks_chain_and_each_expect_lands_on_its_task(
    project: Project, templates: str, body: str, expected: list[tuple[str, dict[str, list[str]]]]
) -> None:
    assert summary(evaluation(project, body, templates)) == expected


def test_checks_on_one_task_merge_as_constraints_do_and_a_file_warns_only_if_every_block_does(project: Project) -> None:
    template = textwrap.dedent("""
        a:
          kind: evaluation
          task: A
          expect:
            - response:
                - words: {min: 50, max: 400}
                - contains: Usage
            - file: {with_path: x.md, severity: warn, lines: {max: 10}}
            - file: {with_path: y.md, severity: warn}
            - file: {with_path: z.md}
    """)
    own = bare(task=None, uses=USES) + textwrap.dedent("""
        expect:
          - response:
              - words: {max: 600}
              - contains: Examples
          - file: {with_path: x.md, lines: {max: 20}}
          - file: {with_path: y.md, severity: warn}
          - file: {with_path: z.md, severity: warn}
    """)
    (task,) = evaluation(project, own, template).tasks
    assert task.expect == (
        Expectation(None, (Check("words", {"min": 50, "max": 600}), contains("Usage"), contains("Examples"))),
        Expectation("x.md", (Check("lines", {"min": None, "max": 20}, "warn"),)),  # the test's block says no warn
        Expectation("y.md", (), "warn"),
        Expectation("z.md"),  # the template's says none
    )


def test_a_templates_run_blocks_come_before_the_tests_on_one_task_each_with_the_directory_of_its_file(project: Project) -> None:
    template = "a: {kind: evaluation, task: A, expect: [{run: pytest}, {response: [{contains: a}]}]}\n"
    own = bare(task=None, uses=USES, expect="[{run: pytest}, {response: [{contains: b}]}, {run: ruff check}]")
    (task,) = evaluation(project, own, template).tasks
    assert task.expect == (
        Run("pytest", project.root),
        Expectation(None, (contains("a"), contains("b"))),
        Run("pytest", project.root / "evals"),
        Run("ruff check", project.root / "evals"),
    )


def test_a_word_list_resolves_from_the_file_declaring_it(project: Project) -> None:
    project.write("banned.txt", "template\n")
    project.write("evals/banned.txt", "test\n")
    expect = "[{response: [{contains_none: {words: ./banned.txt}}]}]"
    (task,) = evaluation(
        project, bare(task=None, uses=USES, expect=expect), f"a: {{kind: evaluation, task: A, expect: {expect}}}\n"
    ).tasks
    assert [check.params["words"] for check in task.expect[0].checks] == [["template"], ["test"]]


@pytest.mark.parametrize("template, body, file, key, said", [
    ("setup: {override_system_prompt: A}", bare(setup="{harness: user_local, append_system_prompt: B}"),
     FILE, "tests.t.setup", "append_system_prompt"),
    ("model: claude-opus-5-5", bare(task=None), FILE, "tests.t.task", "task"),
    ("expect: [{response: [{words: {max: 9}}]}]", bare(), FILE, "tests.t.uses", "template 1"),
    ("max_tokens: 0", bare(), TEMPLATES, "templates.a.max_tokens", "0"),
], ids=["a system prompt on each side", "no task on either side", "an expect with no task above it",
        "a bad value in the template"])
def test_what_shows_once_merged_is_an_error_in_the_test_and_a_bad_template_one_in_its_file(
    project: Project, template: str, body: str, file: str, key: str, said: str
) -> None:
    e = load_error(project, body + f"uses: {USES}\n", f"a: {{kind: evaluation, {template}}}\n")
    assert (e.path, e.key) == (project.root / file, key)
    assert said in e.message


def test_a_templates_judge_block_keeps_the_judge_defaults_of_its_own_file_and_comes_before_the_tests(project: Project) -> None:
    template = "templates:\n  a: {kind: evaluation, task: A, expect: [{judge: 'Right?', require: YES}, {judge: 'Short?', require: YES, effort: max}]}\n"
    project.write(TEMPLATES, "judge_defaults: {model: claude-opus-5-5, effort: low}\n" + template)
    project.write("plain.eval.yml", template)
    defaults = "judge_defaults: {model: claude-haiku-4-5, max_tokens: 5000}\n"
    loaded = with_defaults(project, defaults, uses=f"[{USES}, plain.eval.yml#a]", expect="[{judge: 'Right?', require: YES}]")
    assert [task.expect for task in loaded.tasks] == [
        (Judge("Right?", "YES", model="claude-opus-5-5", effort="low"), Judge("Short?", "YES", model="claude-opus-5-5", effort="max")),
        (Judge("Right?", "YES"), Judge("Short?", "YES", effort="max")),
        (Judge("Right?", "YES", model="claude-haiku-4-5", max_tokens=5000),),
    ]


def test_bad_judge_defaults_of_a_template_file_are_an_error_in_that_file(project: Project) -> None:
    project.write(TEMPLATES, "judge_defaults: {effort: huge}\ntemplates:\n  a: {kind: evaluation}\n")
    with pytest.raises(LoadError) as info:
        with_defaults(project, "", uses=USES)
    assert (info.value.path, info.value.key) == (project.root / TEMPLATES, "judge_defaults.effort")
