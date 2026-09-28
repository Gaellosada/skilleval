"""How `load` turns the keys of an evaluation into `Test.evaluation`: the keys as written, then
the templates merged in. Specified in specs/evaluations.md and specs/templates.md. The static-check
keys an evaluation refuses are rows of test_load.py."""

import textwrap

import pytest
from conftest import Project

from skilleval.testfile import (
    Check,
    Evaluation,
    Expectation,
    FilePrompt,
    LoadError,
    Setup,
    Task,
    TextPrompt,
)

FILE = "evals/t.eval.yml"
TEMPLATES = "shared.eval.yml"
USES = f"{TEMPLATES}#a"
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
    """Write `evals/t.eval.yml`, whose evaluation `t` holds the lines of `body`, and the
    `templates:` entries in `shared.eval.yml` at the root; load and return the evaluation."""
    project.write(TEMPLATES, "root: pyproject.toml\ntemplates:\n" + textwrap.indent(templates, "  "))
    project.tests("t:\n  kind: evaluation\n" + textwrap.indent(textwrap.dedent(body), "  "), FILE)
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
    setup = Setup("user_local", "bypass", FilePrompt(project.root / "prompts/reviewer.md"),
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
        Setup("user_local"), "claude-sonnet-5", (Task("Explain this repository."),), max_budget_usd=0.5
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
    single = "{harness: user_local, override_system_prompt: Be brief., skills: skills/refactor}"
    assert evaluation(project, bare(setup=single)).setup == Setup(
        "user_local", override_system_prompt=TextPrompt("Be brief."), skills=(project.root / "skills/refactor",)
    )


@pytest.mark.parametrize("body, key, offending", [
    (bare(task=None), "tests.t.task", "task"),
    (bare(task="{file: task.md}"), "tests.t.task", "task.md"),
    (bare(task="'  '"), "tests.t.task", "'  '"),
    (bare(model=None), "tests.t.model", "model"),
    (bare(model="[claude-sonnet-5, claude-opus-5-5]"), "tests.t.model", "claude-opus-5-5"),
    (bare(model="'  '"), "tests.t.model", "'  '"),
    (bare(max_tokens="0"), "tests.t.max_tokens", "0"),
    (bare(max_tokens="1.5"), "tests.t.max_tokens", "1.5"),
    (bare(max_tokens="true"), "tests.t.max_tokens", "True"),
    (bare(max_budget_usd="-1"), "tests.t.max_budget_usd", "-1"),
    (bare(max_budget_usd="cheap"), "tests.t.max_budget_usd", "cheap"),
], ids=["no task", "task as a file", "blank task", "no model", "two models", "blank model", "zero tokens",
        "fractional tokens", "boolean tokens", "negative budget", "budget in words"])
def test_task_model_or_limit_missing_or_of_another_shape_is_a_load_error(
    project: Project, body: str, key: str, offending: str
) -> None:
    e = load_error(project, body)
    assert (e.path, e.key) == (project.root / FILE, key)
    assert offending in e.message


@pytest.mark.parametrize("setup, key, offending", [
    ("user_local", "", "user_local"),
    ("{}", ".harness", "harness"),
    ("{harness: claude}", ".harness", "claude"),
    ("{harness: none}", ".harness", "supported"),
    ("{harness: user_local, permissions: sometimes}", ".permissions", "sometimes"),
    ("{harness: user_local, override_system_prompt: A, append_system_prompt: B}", "", "append_system_prompt"),
    ("{harness: user_local, override_system_prompt: {include: '*.md'}}", ".override_system_prompt", "include"),
    ("{harness: user_local, skills: 3}", ".skills", "3"),
    ("{harness: user_local, skills: skills/missing}", ".skills", "skills/missing"),
    ("{harness: user_local, skills: [skills/ok, skills/empty]}", ".skills[1]", "SKILL.md"),
    ("{harness: user_local, skills: [skills/ok/SKILL.md]}", ".skills[0]", "skills/ok/SKILL.md"),
    ("{harness: user_local, working_folder: 3}", ".working_folder", "3"),
    ("{harness: user_local, working_folder: nowhere}", ".working_folder", "nowhere"),
    ("{harness: user_local, working_folder: skills/ok/SKILL.md}", ".working_folder", "skills/ok/SKILL.md"),
    ("{harness: user_local, mcp_servers: {}}", ".mcp_servers", "mcp_servers"),
], ids=["not a mapping", "no harness", "unknown harness", "harness none, not supported yet", "unknown permissions",
        "both system prompts", "system prompt as an include", "skills as a number", "skill that does not exist",
        "skill without a SKILL.md", "skill that is a file", "working folder as a number",
        "working folder that does not exist",
        "working folder that is a file", "unknown key"])
def test_bad_setup_is_a_load_error_at_its_key(project: Project, setup: str, key: str, offending: str) -> None:
    project.write("skills/ok/SKILL.md")
    project.write("skills/empty/notes.md")
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
          - response: [{contains: b}]
            severity: warn
          - file: {with_path: x.md, words: {max: 3}, severity: warn}
          - file: {with_path: "*.md", severity: warn}
          - file: {with_path: "*.md", severity: warn}
          - file: {with_path: y.md}
          - file: {with_path: y.md, severity: warn}
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
    ("[{response: {contains: a}}]", "[0].response", "contains"),
    ("[{response: [chars]}]", "[0].response[0]", "chars"),
    ("[{response: [{words: {max: many}}]}]", "[0].response[0].words.max", "many"),
    ("[{file: {words: {max: 5}}}]", "[0].file.with_path", "with_path"),
    ("[{file: {with_path: ./a.md}}]", "[0].file.with_path", "./a.md"),
    ("[{file: {with_path: /tmp/a.md}}]", "[0].file.with_path", "/tmp/a.md"),
    ("[{file: {with_path: docs/../../a.md}}]", "[0].file.with_path", "docs/../../a.md"),
    ("[{file: {with_path: a.md, severity: fatal}}]", "[0].file.severity", "fatal"),
    ("[{file: {with_path: a.md, lint: [chars]}}]", "[0].file.lint", "lint"),
    ("[{file: {with_path: a.md, words: {max: many}}}]", "[0].file.words.max", "many"),
], ids=["not a list", "block that is not a mapping", "block checking nothing", "block checking two things",
        "unknown block", "bad severity beside response", "response that is not a list", "lint under response",
        "bad parameter under response", "file without with_path", "with_path from the test file",
        "absolute with_path", "with_path climbing out", "bad severity in file", "lint in file",
        "bad parameter in file"])
def test_bad_expect_is_a_load_error_at_its_key(project: Project, expect: str, key: str, offending: str) -> None:
    e = load_error(project, bare(expect=expect))
    assert e.key == "tests.t.expect" + key
    assert offending in e.message


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
            override_system_prompt: {file: ./prompts/reviewer.md}
            skills: [skills/a, skills/b]
            working_folder: one
        b:
          kind: evaluation
          model: claude-haiku-4-5
          max_tokens: 2000
    """))
    setup = Setup("user_local", "bypass", FilePrompt(project.root / "prompts/reviewer.md"),
                  skills=(project.root / "skills/b",), working_folder=project.root / "two")
    assert loaded == Evaluation(setup, "claude-sonnet-5", (Task("Explain this repository."),), 2000, 2)


@pytest.mark.parametrize("templates, body, expected", [
    ("a: {kind: evaluation, task: A}\nb: {kind: evaluation, task: B}\n",
     bare(task="C", uses=f"[{TEMPLATES}#b, {USES}]"), [("B", {}), ("A", {}), ("C", {})]),
    ("a: {kind: evaluation, task: A}\n", bare(task=None, uses=USES), [("A", {})]),
    ("a: {kind: evaluation, task: A, expect: [{response: [{words: {max: 9}}]}]}\n",
     bare(task="C", uses=USES, expect="[{response: [{lines: {max: 9}}]}]"),
     [("A", {"response": ["words"]}), ("C", {"response": ["lines"]})]),
    ("a: {kind: evaluation, task: A}\nb: {kind: evaluation, expect: [{file: {with_path: x.md, lines: {max: 9}}}]}\n",
     bare(task="C", uses=f"[{USES}, {TEMPLATES}#b]"), [("A", {"x.md": ["lines"]}), ("C", {})]),
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


def test_a_word_list_resolves_from_the_file_declaring_it(project: Project) -> None:
    project.write("banned.txt", "template\n")
    project.write("evals/banned.txt", "test\n")
    expect = "[{response: [{contains_none: {words: ./banned.txt}}]}]"
    (task,) = evaluation(
        project, bare(task=None, uses=USES, expect=expect), f"a: {{kind: evaluation, task: A, expect: {expect}}}\n"
    ).tasks
    assert [check.params["words"] for check in task.expect[0].checks] == [["template"], ["test"]]


@pytest.mark.parametrize("template, body, file, key", [
    ("setup: {override_system_prompt: A}", bare(setup="{harness: user_local, append_system_prompt: B}"),
     FILE, "tests.t.setup"),
    ("model: claude-opus-5-5", bare(task=None), FILE, "tests.t.task"),
    ("expect: [{response: [{words: {max: 9}}]}]", bare(), FILE, "tests.t.uses"),
    ("max_tokens: 0", bare(), TEMPLATES, "templates.a.max_tokens"),
], ids=["a system prompt on each side", "no task on either side", "an expect with no task above it",
        "a bad value in the template"])
def test_what_shows_once_merged_is_an_error_in_the_test_and_a_bad_template_one_in_its_file(
    project: Project, template: str, body: str, file: str, key: str
) -> None:
    e = load_error(project, body + f"uses: {USES}\n", f"a: {{kind: evaluation, {template}}}\n")
    assert (e.path, e.key) == (project.root / file, key)
