"""Templates and `uses`, through `skilleval.testfile.load`. Specified in specs/templates.md.
File-level template validation (a template that is not a mapping, a missing or unknown `kind`) and a
root-relative `uses` path without `root` are rows of test_load.py."""

import textwrap
from collections import Counter
from pathlib import Path

import pytest
from conftest import Project

from skilleval import testfile
from skilleval.testfile.document import read_document
from skilleval.testfile.templates import read_templates

TEST = "tests:\n  t:\n    kind: static-check\n    prompt: hi\n"
STATIC = "tpl:\n  kind: static-check\n"
USES = "uses: ./shared.eval.yml#tpl\n"
CHARS = testfile.Check("chars")
WORDS_400 = testfile.Check("words", {"min": None, "max": 400})
WORDS_600 = testfile.Check("words", {"min": None, "max": 600})


def load_using(project: Project, templates: str, test: str) -> testfile.Test:
    """Write `shared.eval.yml` holding the `templates:` body and `t.eval.yml` holding a static-check
    `t` with a text prompt plus the `test` lines (`uses` among them); load and return `t`."""
    project.write("shared.eval.yml", "templates:\n" + textwrap.indent(textwrap.dedent(templates), "  "))
    project.write("t.eval.yml", TEST + textwrap.indent(textwrap.dedent(test), "    "))
    return project.load("t.eval.yml").tests["t"]


# Files that define templates


def test_template_only_file_loads_with_no_tests(project: Project) -> None:
    project.write("shared.eval.yml", "templates:\n  house_style:\n    kind: static-check\n    lint: [chars]\n")
    assert project.load("shared.eval.yml").tests == {}


def test_file_can_define_templates_and_tests_and_a_template_applies_only_through_uses(project: Project) -> None:
    project.write("both.eval.yml", """
        templates:
          house_style:
            kind: static-check
            lint: [chars]
        tests:
          skills:
            kind: static-check
            prompt: hi
            constraints:
              - words:
                  max: 400
    """)
    loaded = project.load("both.eval.yml")
    assert list(loaded.tests) == ["skills"]
    assert loaded.tests["skills"].checks == (WORDS_400,)


def test_test_can_use_a_template_from_its_own_file(project: Project) -> None:
    project.write("both.eval.yml", """
        templates:
          house_style:
            kind: static-check
            lint: [chars]
        tests:
          skills:
            kind: static-check
            prompt: hi
            uses: ./both.eval.yml#house_style
    """)
    assert project.load("both.eval.yml").tests["skills"].checks == (CHARS,)


def test_read_templates_reads_the_templates_section_and_never_the_tests(project: Project) -> None:
    path = project.write("both.eval.yml", """
        templates:
          tpl:
            kind: static-check
            lint: [chars]
        tests:
          broken:
            kind: nope
    """)
    assert read_templates(read_document(path), path) == {"tpl": ("static-check", (CHARS,))}


# `uses`: one reference or a list, each path#template


@pytest.mark.parametrize("templates, test, expected", [
    (STATIC, USES, ()),
    (STATIC + "  lint: [chars]", USES, (CHARS,)),
    ("a:\n  kind: static-check\n  lint: [chars]\nb:\n  kind: static-check\n  lint: [markdown_links]",
     "uses: [./shared.eval.yml#a, ./shared.eval.yml#b]", (CHARS, testfile.Check("markdown_links"))),
    (STATIC, "uses: []\nlint: [chars]", (CHARS,)),
], ids=["template with only a kind adds nothing", "one reference", "a list", "an empty list adds nothing"])
def test_uses_takes_one_reference_or_a_list(project: Project, templates: str, test: str, expected: tuple) -> None:
    assert load_using(project, templates, test).checks == expected


@pytest.mark.parametrize("real, decoy, head, reference", [
    ("evals/shared.eval.yml", "shared.eval.yml", "", "./shared.eval.yml#tpl"),
    ("shared/tpl.eval.yml", "evals/shared/tpl.eval.yml", "root: pyproject.toml\n", "shared/tpl.eval.yml#tpl"),
], ids=["dot-slash from the test file", "root-relative from the project root"])
def test_uses_path_resolves_from_the_test_file_or_the_project_root(project: Project, real: str, decoy: str, head: str, reference: str) -> None:
    project.write(real, "templates:\n  tpl:\n    kind: static-check\n    lint: [chars]\n")
    project.write(decoy, "templates:\n  tpl:\n    kind: static-check\n    lint: [paths_exist]\n")
    project.write("evals/t.eval.yml", head + TEST + f"    uses: {reference}\n")
    assert project.load("evals/t.eval.yml").tests["t"].checks == (CHARS,)


@pytest.mark.parametrize("uses, key, offending", [
    ("./missing.eval.yml#tpl", "tests.t.uses", "missing.eval.yml"),
    ("./shared.eval.yml", "tests.t.uses", "shared.eval.yml"),
    ("./shared.eval.yml#nope", "tests.t.uses", "nope"),
    ("./shared.eval.yml#", "tests.t.uses", "shared.eval.yml#"),
    ("[./shared.eval.yml#tpl, ./shared.eval.yml#nope]", "tests.t.uses[1]", "nope"),
    ("{path: ./shared.eval.yml}", "tests.t.uses", None),
], ids=["missing file", "no hash", "unknown template", "no name", "unknown template in a list", "neither string nor list"])
def test_bad_uses_reference_is_an_error_at_its_key(project: Project, uses: str, key: str, offending: str | None) -> None:
    with pytest.raises(testfile.LoadError) as info:
        load_using(project, STATIC, f"uses: {uses}")
    assert info.value.key == key
    assert offending is None or offending in info.value.message


# Template validation


@pytest.mark.parametrize("key, value", [
    ("prompt", "hi"), ("tasks", "./tasks/*.yml"), ("needs", "other"), ("uses", "./other.eval.yml#x"), ("name", "House style"), ("nonsense", "1"),
])
def test_template_with_a_target_an_identity_or_an_unknown_key_is_an_error(project: Project, key: str, value: str) -> None:
    with pytest.raises(testfile.LoadError) as info:
        load_using(project, STATIC + f"  {key}: {value}", USES)
    assert info.value.key == f"templates.tpl.{key}"
    assert key in info.value.message


def test_template_of_another_kind_than_the_test_is_an_error(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skilleval.testfile.document.KINDS", frozenset({"static-check", "other"}))
    with pytest.raises(testfile.LoadError) as info:
        load_using(project, "tpl:\n  kind: other\n", USES)
    assert info.value.key == "tests.t.uses"
    assert "other" in info.value.message


def test_template_checks_are_validated_like_a_tests(project: Project) -> None:
    with pytest.raises(testfile.LoadError) as info:
        load_using(project, STATIC + '  constraints:\n    - words: {max: "x"}', USES)
    assert info.value.path == project.root / "shared.eval.yml"
    assert info.value.key == "templates.tpl.constraints[0].words.max"
    assert "x" in info.value.message


# Merging


def test_spec_example_merges_to_the_exact_checks(project: Project) -> None:
    test = load_using(
        project,
        """
        tpl:
          kind: static-check
          lint: [chars, markdown_links, paths_exist]
          constraints:
            - words:
                max: 400
        """,
        """
        uses: ./shared.eval.yml#tpl
        lint:
          - paths_exist:
              severity: warn
        constraints:
          - words:
              max: 600
        """,
    )
    assert test.checks == (CHARS, testfile.Check("markdown_links"), testfile.Check("paths_exist", {}, "warn"), WORDS_600)


def test_lint_then_format_then_constraints_with_template_entries_first(project: Project) -> None:
    test = load_using(
        project,
        """
        tpl:
          kind: static-check
          lint: [chars]
          format: anthropic-skill
          constraints:
            - words:
                max: 400
                severity: warn
        """,
        """
        uses: ./shared.eval.yml#tpl
        lint: [markdown_links]
        constraints:
          - lines:
              max: 10
        """,
    )
    assert test.checks == (
        CHARS,
        testfile.Check("markdown_links"),
        testfile.Check("anthropic-skill"),
        testfile.Check("words", {"min": None, "max": 400}, "warn"),
        testfile.Check("lines", {"min": None, "max": 10}),
    )


@pytest.mark.parametrize("template, own, expected", [
    ("lint: [paths_exist]", "lint: [{paths_exist: {severity: warn}}]", "warn"),
    ("lint: [{paths_exist: {severity: warn}}]", "lint: [{paths_exist: {severity: error}}]", "error"),
    ("lint: [{paths_exist: {severity: warn}}]", "lint: [paths_exist]", "warn"),
], ids=["the test downgrades to warn", "the test raises to error", "a test writing no severity keeps the template's"])
def test_lint_named_on_both_sides_takes_the_severity_the_test_writes(
    project: Project, template: str, own: str, expected: str
) -> None:
    test = load_using(project, STATIC + "  " + template, USES + own)
    assert test.checks == (testfile.Check("paths_exist", {}, expected),)


def test_lint_warned_only_in_the_template_stays_a_warning(project: Project) -> None:
    test = load_using(project, STATIC + "  lint: [{paths_exist: {severity: warn}}]", USES)
    assert test.checks == (testfile.Check("paths_exist", {}, "warn"),)


@pytest.mark.parametrize("own, expected", [
    ("format: anthropic-claude", testfile.Check("anthropic-claude")),
    ("format: {anthropic-skill: {severity: warn}}", testfile.Check("anthropic-skill", {}, "warn")),
    ("", testfile.Check("anthropic-skill")),
], ids=["another format replaces it", "the same format at warn downgrades it", "no format of its own keeps it"])
def test_the_tests_format_overrides_the_templates(project: Project, own: str, expected: testfile.Check) -> None:
    assert load_using(project, STATIC + "  format: anthropic-skill", USES + own).checks == (expected,)


def test_a_later_templates_format_overrides_an_earlier_ones(project: Project) -> None:
    templates = "a:\n  kind: static-check\n  format: anthropic-skill\nb:\n  kind: static-check\n  format: anthropic-claude"
    test = load_using(project, templates, "uses: [./shared.eval.yml#a, ./shared.eval.yml#b]")
    assert test.checks == (testfile.Check("anthropic-claude"),)


@pytest.mark.parametrize("template, own, expected", [
    ("words: {max: 400}", "words: {max: 600}", (WORDS_600,)),
    ("words: {min: 50, max: 400}", "words: {max: 600}", (testfile.Check("words", {"min": 50, "max": 600}),)),
    ("words: {max: 400, severity: warn}", "words: {max: 600}", (testfile.Check("words", {"min": None, "max": 600}, "warn"),)),
    ("words: {max: 400, severity: warn}", "words: {max: 600, severity: error}", (testfile.Check("words", {"min": None, "max": 600}, "error"),)),
    ("paths: {style: posix, except: ['a/**']}", "paths: {count: {max: 1}}",
     (testfile.Check("paths", {"style": "posix", "except": ["a/**"], "count": {"min": None, "max": 1}}),)),
    ("words: {max: 400}\n    - words: {max: 500, severity: warn}", "words: {max: 600}",
     (WORDS_600, testfile.Check("words", {"min": None, "max": 600}, "warn"))),
    ("contains: Usage", "contains: Examples",
     (testfile.Check("contains", {"words": ["Usage"], "occurrences": {"min": 1, "max": None}, "case_sensitive": False}),
      testfile.Check("contains", {"words": ["Examples"], "occurrences": {"min": 1, "max": None}, "case_sensitive": False}))),
], ids=["the test's max replaces the template's", "a parameter only the template sets is kept", "severity the test does not write is the template's",
        "severity the test writes wins", "parameters merge on paths too", "the test overrides each of several template entries", "contains is additive"])
def test_a_constraint_on_both_sides_overrides_parameter_by_parameter_but_contains_and_matches_add(
    project: Project, template: str, own: str, expected: tuple
) -> None:
    test = load_using(project, STATIC + "  constraints:\n    - " + template, USES + "constraints:\n  - " + own)
    assert test.checks == expected


def test_several_uses_apply_in_order(project: Project) -> None:
    test = load_using(
        project,
        """
        a:
          kind: static-check
          lint: [chars]
          constraints:
            - words: {max: 400}
        b:
          kind: static-check
          lint: [markdown_links]
          constraints:
            - lines: {max: 100}
        """,
        """
        uses: [./shared.eval.yml#b, ./shared.eval.yml#a]
        lint: [paths_exist]
        constraints:
          - words: {max: 600}
        """,
    )
    names = tuple(c.name for c in test.checks)
    assert names == ("markdown_links", "chars", "paths_exist", "lines", "words")


def test_a_later_template_overrides_an_earlier_one(project: Project) -> None:
    test = load_using(
        project,
        """
        soft:
          kind: static-check
          lint: [{paths_exist: {severity: warn}}]
        hard:
          kind: static-check
          lint: [{paths_exist: {severity: error}}]
        """,
        "uses: [./shared.eval.yml#soft, ./shared.eval.yml#hard]",
    )
    assert test.checks == (testfile.Check("paths_exist", {}, "error"),)


# Paths inside a template resolve against the template's own file and its own root


def test_dot_slash_path_in_a_template_resolves_from_the_template_file(project: Project) -> None:
    project.write("shared/banned.txt", "foo\nbar\n")
    project.write("evals/banned.txt", "decoy\n")
    project.write("shared/tpl.eval.yml", """
        templates:
          tpl:
            kind: static-check
            constraints:
              - contains_none:
                  words: ./banned.txt
    """)
    project.write("evals/t.eval.yml", TEST + "    uses: ./../shared/tpl.eval.yml#tpl\n")
    (check,) = project.load("evals/t.eval.yml").tests["t"].checks
    assert check.name == "contains_none"
    assert check.params["words"] == ["foo", "bar"]


def test_root_relative_path_in_a_template_resolves_from_the_templates_own_root(project: Project) -> None:
    project.write("lists/banned.txt", "decoy\n")
    project.write("shared/marker", "")
    project.write("shared/lists/banned.txt", "foo\n")
    project.write("shared/tpl.eval.yml", """
        root: marker
        templates:
          tpl:
            kind: static-check
            constraints:
              - contains_none:
                  words: lists/banned.txt
    """)
    project.write("t.eval.yml", "root: pyproject.toml\n" + TEST + "    uses: ./shared/tpl.eval.yml#tpl\n")
    (check,) = project.load("t.eval.yml").tests["t"].checks
    assert check.params["words"] == ["foo"]


def test_root_relative_path_in_a_template_file_without_root_is_an_error(project: Project) -> None:
    project.write("lists/banned.txt", "foo\n")
    project.write("shared.eval.yml", """
        templates:
          tpl:
            kind: static-check
            constraints:
              - contains_none:
                  words: lists/banned.txt
    """)
    project.write("t.eval.yml", "root: pyproject.toml\n" + TEST + "    uses: ./shared.eval.yml#tpl\n")
    with pytest.raises(testfile.LoadError) as info:
        project.load("t.eval.yml")
    assert info.value.path == project.root / "shared.eval.yml"
    assert info.value.key == "templates.tpl.constraints[0].contains_none.words"
    assert "banned.txt" in info.value.message


def test_template_name_that_yaml_reads_as_another_type_is_a_load_error_naming_it(project: Project) -> None:
    path = project.write("shared.eval.yml", "templates:\n  on:\n    kind: static-check\n")
    with pytest.raises(testfile.LoadError) as info:
        testfile.load(path)
    assert info.value.key == "templates"
    assert "True" in info.value.message


def test_each_file_is_read_once_per_load(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("shared.eval.yml", "templates:\n  tpl:\n    kind: static-check\n    lint: [chars]\n")
    tests = "".join(f"  t{i}:\n    kind: static-check\n    prompt: hi\n    uses: ./shared.eval.yml#tpl\n" for i in range(3))
    project.write("t.eval.yml", "tests:\n" + tests)
    reads: Counter[str] = Counter()
    read_text = Path.read_text

    def counting(self: Path, *args: object, **kwargs: object) -> str:
        reads[self.name] += 1
        return read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting)
    project.load("t.eval.yml")
    assert reads == {"t.eval.yml": 1, "shared.eval.yml": 1}
