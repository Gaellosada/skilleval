"""Templates and `uses`, through `skilleval.testfile.load`. Specified in specs/templates.md."""

from __future__ import annotations

import textwrap

import pytest
from conftest import Project

from skilleval import testfile

TEST = "tests:\n  t:\n    kind: static-check\n    prompt: {text: hi}\n"


def load_using(project: Project, templates: str, test: str) -> testfile.Test:
    """Write `shared.eval.yml` holding the `templates:` body and `t.eval.yml` holding a static-check
    `t` with a text prompt plus the `test` lines (`uses` among them); load and return `t`."""
    project.write("shared.eval.yml", "templates:\n" + textwrap.indent(textwrap.dedent(templates), "  "))
    project.write("t.eval.yml", TEST + textwrap.indent(textwrap.dedent(test), "    "))
    return project.load("t.eval.yml").tests["t"]


def using_error(project: Project, templates: str, test: str) -> testfile.LoadError:
    with pytest.raises(testfile.LoadError) as info:
        load_using(project, templates, test)
    return info.value


def words(maximum: int, severity: str = "error") -> testfile.Check:
    return testfile.Check("words", {"min": None, "max": maximum}, severity)


STATIC = "tpl:\n  kind: static-check\n"
USES = "uses: ./shared.eval.yml#tpl\n"


# --- files that define templates ---------------------------------------------------------


def test_template_only_file_loads_with_no_tests(project: Project) -> None:
    project.write("shared.eval.yml", """
        templates:
          house_style:
            kind: static-check
            lint: [chars]
    """)
    assert project.load("shared.eval.yml").tests == {}


def test_file_can_define_templates_and_tests(project: Project) -> None:
    project.write("both.eval.yml", """
        templates:
          house_style:
            kind: static-check
            lint: [chars]
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
            constraints:
              - words:
                  max: 400
    """)
    loaded = project.load("both.eval.yml")
    assert list(loaded.tests) == ["skills"]
    assert loaded.tests["skills"].checks == (words(400),)


def test_test_can_use_a_template_from_its_own_file(project: Project) -> None:
    project.write("both.eval.yml", """
        templates:
          house_style:
            kind: static-check
            lint: [chars]
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
            uses: ./both.eval.yml#house_style
    """)
    assert project.load("both.eval.yml").tests["skills"].checks == (testfile.Check("chars"),)


def test_template_with_only_a_kind_adds_nothing(project: Project) -> None:
    assert load_using(project, STATIC, USES).checks == ()


# --- `uses`: one reference or a list, each path#template -------------------------------


def test_uses_one_reference(project: Project) -> None:
    assert load_using(project, STATIC + "  lint: [chars]", USES).checks == (testfile.Check("chars"),)


def test_uses_a_list_of_references(project: Project) -> None:
    test = load_using(
        project,
        """
        a:
          kind: static-check
          lint: [chars]
        b:
          kind: static-check
          lint: [markdown_links]
        """,
        "uses: [./shared.eval.yml#a, ./shared.eval.yml#b]",
    )
    assert test.checks == (testfile.Check("chars"), testfile.Check("markdown_links"))


def test_uses_an_empty_list_adds_nothing(project: Project) -> None:
    assert load_using(project, STATIC, "uses: []\nlint: [chars]").checks == (testfile.Check("chars"),)


def test_dot_slash_uses_path_resolves_from_the_test_file_not_the_cwd(project: Project) -> None:
    project.write("shared.eval.yml", """
        templates:
          tpl:
            kind: static-check
            lint: [paths_exist]
    """)
    project.write("evals/shared.eval.yml", """
        templates:
          tpl:
            kind: static-check
            lint: [chars]
    """)
    project.write("evals/t.eval.yml", TEST + "    uses: ./shared.eval.yml#tpl\n")
    assert project.load("evals/t.eval.yml").tests["t"].checks == (testfile.Check("chars"),)


def test_root_relative_uses_path_resolves_from_the_project_root(project: Project) -> None:
    project.write("shared/tpl.eval.yml", """
        templates:
          tpl:
            kind: static-check
            lint: [chars]
    """)
    project.write("evals/t.eval.yml", "root: pyproject.toml\n" + TEST + "    uses: shared/tpl.eval.yml#tpl\n")
    assert project.load("evals/t.eval.yml").tests["t"].checks == (testfile.Check("chars"),)


def test_root_relative_uses_path_without_root_is_an_error(project: Project) -> None:
    e = using_error(project, STATIC, "uses: shared.eval.yml#tpl")
    assert e.key == "tests.t.uses"
    assert "shared.eval.yml" in str(e)


@pytest.mark.parametrize(
    ("reference", "offending"),
    [
        ("./missing.eval.yml#tpl", "missing.eval.yml"),
        ("./shared.eval.yml", "shared.eval.yml"),
        ("./shared.eval.yml#nope", "nope"),
        ("./shared.eval.yml#", "shared.eval.yml#"),
    ],
    ids=["missing file", "no hash", "unknown template", "no name"],
)
def test_bad_uses_reference_is_an_error(project: Project, reference: str, offending: str) -> None:
    e = using_error(project, STATIC, f"uses: {reference}")
    assert e.key == "tests.t.uses"
    assert offending in str(e)


def test_bad_reference_in_a_uses_list_is_keyed_by_index(project: Project) -> None:
    e = using_error(project, STATIC, "uses: [./shared.eval.yml#tpl, ./shared.eval.yml#nope]")
    assert e.key == "tests.t.uses[1]"
    assert "nope" in str(e)


def test_uses_that_is_neither_a_string_nor_a_list_is_an_error(project: Project) -> None:
    assert using_error(project, STATIC, "uses:\n  path: ./shared.eval.yml").key == "tests.t.uses"


# --- template validation -----------------------------------------------------------------


def test_template_that_is_not_a_mapping_is_an_error(project: Project) -> None:
    project.write("shared.eval.yml", "templates:\n  tpl: [chars]\n")
    with pytest.raises(testfile.LoadError) as e:
        project.load("shared.eval.yml")
    assert e.value.key == "templates.tpl"


@pytest.mark.parametrize(
    ("body", "offending"),
    [("lint: [chars]", "kind"), ("kind: nope", "nope"), ("kind: evaluation", "evaluation"), ("kind: benchmark", "benchmark")],
    ids=["missing", "unknown", "evaluation", "benchmark"],
)
def test_template_kind_missing_unknown_or_not_static_check_is_an_error(project: Project, body: str, offending: str) -> None:
    project.write("shared.eval.yml", f"templates:\n  tpl:\n    {body}\n")
    with pytest.raises(testfile.LoadError) as e:
        project.load("shared.eval.yml")
    assert e.value.key == "templates.tpl.kind"
    assert offending in str(e.value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("prompt", "{text: hi}"),
        ("tasks", "./tasks/*.yml"),
        ("name", "House style"),
        ("needs", "other"),
        ("uses", "./other.eval.yml#x"),
        ("nonsense", "1"),
    ],
    ids=["prompt", "tasks", "name", "needs", "uses", "unknown key"],
)
def test_template_with_a_forbidden_key_is_an_error(project: Project, key: str, value: str) -> None:
    project.write("shared.eval.yml", f"templates:\n  tpl:\n    kind: static-check\n    {key}: {value}\n")
    with pytest.raises(testfile.LoadError) as e:
        project.load("shared.eval.yml")
    assert e.value.key == f"templates.tpl.{key}"
    assert key in str(e.value)


def test_template_checks_are_validated_like_a_tests(project: Project) -> None:
    e = using_error(project, STATIC + '  constraints:\n    - words: {max: "x"}', USES)
    assert e.path == project.root / "shared.eval.yml"
    assert e.key == "templates.tpl.constraints[0].words.max"
    assert "x" in str(e)


# --- merging -----------------------------------------------------------------------------


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
    assert test.checks == (
        testfile.Check("chars"),
        testfile.Check("markdown_links"),
        testfile.Check("paths_exist"),
        words(400),
        words(600),
    )


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
        testfile.Check("chars"),
        testfile.Check("markdown_links"),
        testfile.Check("anthropic-skill"),
        words(400, "warn"),
        testfile.Check("lines", {"min": None, "max": 10}),
    )


@pytest.mark.parametrize(
    ("entry", "name"),
    [
        ("lint: [{paths_exist: {severity: %s}}]", "paths_exist"),
        ("format: {anthropic-skill: {severity: %s}}", "anthropic-skill"),
    ],
    ids=["lint", "format"],
)
@pytest.mark.parametrize(
    ("template_severity", "test_severity", "expected"),
    [
        ("error", "warn", "error"),
        ("warn", "error", "error"),
        ("warn", "warn", "warn"),
    ],
)
def test_rule_named_on_both_sides_keeps_the_stricter_severity(
    project: Project, entry: str, name: str, template_severity: str, test_severity: str, expected: str
) -> None:
    test = load_using(project, STATIC + "  " + entry % template_severity, USES + entry % test_severity)
    assert test.checks == (testfile.Check(name, {}, expected),)


def test_lint_warned_only_in_the_template_stays_a_warning(project: Project) -> None:
    test = load_using(project, STATIC + "  lint: [{paths_exist: {severity: warn}}]", USES)
    assert test.checks == (testfile.Check("paths_exist", {}, "warn"),)


def test_different_formats_on_both_sides_are_unioned(project: Project) -> None:
    test = load_using(project, STATIC + "  format: anthropic-skill", USES + "format: anthropic-claude")
    assert test.checks == (testfile.Check("anthropic-skill"), testfile.Check("anthropic-claude"))


def test_constraints_from_both_sides_both_stand(project: Project) -> None:
    test = load_using(
        project,
        STATIC + "  constraints:\n    - words: {max: 400}",
        USES + "constraints:\n  - words: {max: 400}\n  - words: {max: 600}",
    )
    assert test.checks == (words(400), words(400), words(600))


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
    assert names == ("markdown_links", "chars", "paths_exist", "lines", "words", "words")


def test_stricter_severity_wins_across_two_templates(project: Project) -> None:
    test = load_using(
        project,
        """
        soft:
          kind: static-check
          lint: [{paths_exist: {severity: warn}}]
        hard:
          kind: static-check
          lint: [paths_exist]
        """,
        "uses: [./shared.eval.yml#soft, ./shared.eval.yml#hard]",
    )
    assert test.checks == (testfile.Check("paths_exist"),)


# --- paths inside a template ------------------------------------------------------------


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
    project.write("evals/t.eval.yml", TEST + "    uses: ../shared/tpl.eval.yml#tpl\n")
    (check,) = project.load("evals/t.eval.yml").tests["t"].checks
    assert check.name == "contains_none"
    assert check.params["words"] == ["foo", "bar"]


def test_root_relative_path_in_a_template_resolves_from_the_templates_own_root(project: Project) -> None:
    project.write("banned.txt", "decoy\n")
    project.write("shared/marker", "")
    project.write("shared/banned.txt", "foo\n")
    project.write("shared/tpl.eval.yml", """
        root: marker
        templates:
          tpl:
            kind: static-check
            constraints:
              - contains_none:
                  words: banned.txt
    """)
    project.write("t.eval.yml", "root: pyproject.toml\n" + TEST + "    uses: ./shared/tpl.eval.yml#tpl\n")
    (check,) = project.load("t.eval.yml").tests["t"].checks
    assert check.params["words"] == ["foo"]


def test_root_relative_path_in_a_template_file_without_root_is_an_error(project: Project) -> None:
    project.write("banned.txt", "foo\n")
    project.write("shared.eval.yml", """
        templates:
          tpl:
            kind: static-check
            constraints:
              - contains_none:
                  words: banned.txt
    """)
    project.write("t.eval.yml", "root: pyproject.toml\n" + TEST + "    uses: ./shared.eval.yml#tpl\n")
    with pytest.raises(testfile.LoadError) as e:
        project.load("t.eval.yml")
    assert e.value.path == project.root / "shared.eval.yml"
    assert e.value.key == "templates.tpl.constraints[0].contains_none.words"
    assert "banned.txt" in str(e.value)
