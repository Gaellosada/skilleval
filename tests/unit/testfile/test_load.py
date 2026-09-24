"""`skilleval.testfile.load`: file level, test entries, prompt forms and path resolution as
`load` applies it. Check parameters and templates are covered elsewhere."""

from pathlib import Path

import pytest

from skilleval.testfile import FilePrompt, GlobPrompt, LoadError, TextPrompt, load

STATIC = """
    tests:
      skills:
        kind: static-check
        prompt: {text: hi}
"""


def load_error(path: Path) -> LoadError:
    with pytest.raises(LoadError) as info:
        load(path)
    return info.value


# File level


def test_test_file_fields(project):
    path = project.write("skills.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
    """)
    tf = load(path)
    assert tf.path == path
    assert tf.root == project.root
    assert list(tf.tests) == ["skills"]


def test_root_is_none_without_the_key(project):
    assert load(project.write("t.eval.yml", STATIC)).root is None


def test_unknown_top_level_key_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "    extra: 1\n"))
    assert e.key == "extra"
    assert "extra" in e.message


@pytest.mark.parametrize("text, key", [
    (STATIC + "    name: Skills\n", "name"),
    (STATIC + "        name: Every skill file\n", "tests.skills.name"),
], ids=["file", "test"])
def test_name_is_an_unknown_key(project, text, key):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert "name" in e.message


def test_file_without_tests_or_templates_is_a_load_error(project):
    assert load_error(project.write("t.eval.yml", "root: pyproject.toml\n")).key == "tests"


@pytest.mark.parametrize("text", ["- a\n", "a\n", "tests: [\n", ""], ids=["list", "scalar", "invalid yaml", "empty"])
def test_document_that_is_not_a_mapping_is_a_load_error_naming_the_file(project, text):
    path = project.write("t.eval.yml", text)
    e = load_error(path)
    assert e.key == ""
    assert str(e) == f"{path}: {e.message}"


@pytest.mark.parametrize("text, key, value", [
    ("""
        root: pyproject.toml
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
    """, "root", "root"),
    ("""
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
          skills:
            kind: static-check
            prompt: {text: hi}
    """, "tests.skills", "skills"),
], ids=["top level", "test id"])
def test_duplicate_key_anywhere_is_a_load_error(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


def test_tests_must_be_a_mapping(project):
    assert load_error(project.write("t.eval.yml", "tests: [skills]\n")).key == "tests"


def test_test_entry_must_be_a_mapping(project):
    e = load_error(project.write("t.eval.yml", "tests:\n  skills: static-check\n"))
    assert e.key == "tests.skills"


# Test entries


def test_id_and_kind(project):
    t = load(project.write("t.eval.yml", STATIC)).tests["skills"]
    assert (t.id, t.kind) == ("skills", "static-check")


@pytest.mark.parametrize("kind", ["evaluation", "benchmark", "lint"])
def test_kind_other_than_static_check_is_a_load_error_naming_path_key_and_value(project, kind):
    path = project.write("t.eval.yml", f"tests:\n  skills:\n    kind: {kind}\n    prompt: {{text: hi}}\n")
    e = load_error(path)
    assert e.path == path
    assert e.key == "tests.skills.kind"
    assert kind in e.message
    assert str(e) == f"{path}: tests.skills.kind: {e.message}"


def test_missing_kind_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", "tests:\n  skills:\n    prompt: {text: hi}\n"))
    assert e.key == "tests.skills.kind"


@pytest.mark.parametrize("key", ["extra", "setup", "tasks"])
def test_unknown_key_on_a_static_check_is_a_load_error(project, key):
    e = load_error(project.write("t.eval.yml", STATIC + f"        {key}: x\n"))
    assert e.key == f"tests.skills.{key}"
    assert key in e.message


def test_static_check_without_checks_has_none(project):
    assert load(project.write("t.eval.yml", STATIC)).tests["skills"].checks == ()


def test_needs_one_id(project):
    t = load(project.write("t.eval.yml", STATIC + """
      style:
        kind: static-check
        prompt: {text: hi}
        needs: skills
    """)).tests["style"]
    assert t.needs == ("skills",)


def test_needs_a_list(project):
    t = load(project.write("t.eval.yml", STATIC + """
      style:
        kind: static-check
        prompt: {text: hi}
      links:
        kind: static-check
        prompt: {text: hi}
        needs: [skills, style]
    """)).tests["links"]
    assert t.needs == ("skills", "style")


@pytest.mark.parametrize("needs", ["", "        needs: []\n"], ids=["absent", "empty list"])
def test_needs_absent_or_empty_is_an_empty_tuple(project, needs):
    assert load(project.write("t.eval.yml", STATIC + needs)).tests["skills"].needs == ()


def test_needs_unknown_id_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "        needs: nope\n"))
    assert e.key == "tests.skills.needs"
    assert "nope" in e.message


def test_needs_unknown_id_in_a_list_is_keyed_by_index(project):
    e = load_error(project.write("t.eval.yml", STATIC + """
      style:
        kind: static-check
        prompt: {text: hi}
        needs: [skills, nope]
    """))
    assert e.key == "tests.style.needs[1]"
    assert "nope" in e.message


def test_needs_self_reference_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "        needs: skills\n"))
    assert e.key == "tests.skills.needs"
    assert "skills" in e.message


def test_needs_cycle_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
            needs: style
          style:
            kind: static-check
            prompt: {text: hi}
            needs: skills
    """))
    assert e.key in ("tests.skills.needs", "tests.style.needs")


def test_tests_keep_file_order_without_needs(project):
    tf = load(project.write("t.eval.yml", """
        tests:
          c: {kind: static-check, prompt: {text: hi}}
          a: {kind: static-check, prompt: {text: hi}}
          b: {kind: static-check, prompt: {text: hi}}
    """))
    assert list(tf.tests) == ["c", "a", "b"]


def test_tests_put_a_needed_test_before_the_one_needing_it(project):
    tf = load(project.write("t.eval.yml", """
        tests:
          c: {kind: static-check, prompt: {text: hi}, needs: a}
          a: {kind: static-check, prompt: {text: hi}}
          b: {kind: static-check, prompt: {text: hi}}
    """))
    assert list(tf.tests) == ["a", "c", "b"]


def test_tests_put_a_chain_of_needs_in_dependency_order(project):
    tf = load(project.write("t.eval.yml", """
        tests:
          c: {kind: static-check, prompt: {text: hi}, needs: b}
          b: {kind: static-check, prompt: {text: hi}, needs: a}
          a: {kind: static-check, prompt: {text: hi}}
    """))
    assert list(tf.tests) == ["a", "b", "c"]


# Prompt forms


def test_literal_path_prompt_is_a_file_prompt_never_globbed(project):
    t = load(project.write("t.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: skills/*.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "skills/*.md")


def test_text_prompt(project):
    t = load(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt:
              text: |
                # Title
                body
    """)).tests["skills"]
    assert t.prompt == TextPrompt("# Title\nbody\n")


@pytest.mark.parametrize("exclude, expected", [
    ("", ()),
    ('exclude: "**/fixtures/**"', ("**/fixtures/**",)),
    ('exclude: ["**/fixtures/**", "**/legacy/**"]', ("**/fixtures/**", "**/legacy/**")),
], ids=["none", "one", "list"])
def test_glob_prompt_exclude_is_always_a_tuple(project, exclude, expected):
    t = load(project.write("t.eval.yml", f"""
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt:
              include: "**/SKILL.md"
              {exclude}
    """)).tests["skills"]
    assert t.prompt == GlobPrompt(project.root, "**/SKILL.md", expected)


def test_glob_prompt_include_prefixed_with_dot_slash_is_based_on_the_test_file(project):
    t = load(project.write("sub/t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt:
              include: ./skills/**/SKILL.md
    """)).tests["skills"]
    assert t.prompt == GlobPrompt(project.root / "sub", "skills/**/SKILL.md", ())


@pytest.mark.parametrize("prompt", ["[SKILL.md]", "3", "{}", '{exclude: "**/fixtures/**"}', "{text: hi, include: ./SKILL.md}"])
def test_prompt_of_another_shape_is_a_load_error(project, prompt):
    e = load_error(project.write("t.eval.yml", f"tests:\n  skills:\n    kind: static-check\n    prompt: {prompt}\n"))
    assert e.key == "tests.skills.prompt"


def test_prompt_unknown_key_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: {text: hi, extra: 1}
    """))
    assert e.key == "tests.skills.prompt.extra"
    assert "extra" in e.message


def test_missing_prompt_on_a_static_check_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", "tests:\n  skills:\n    kind: static-check\n"))
    assert e.key == "tests.skills.prompt"


# Root and path resolution


def test_dot_slash_path_is_relative_to_the_test_file(project):
    t = load(project.write("sub/t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: ./SKILL.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "sub" / "SKILL.md")


def test_root_marker_never_found_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "    root: no-such-marker.xyz\n"))
    assert e.key == "root"
    assert "no-such-marker.xyz" in e.message


def test_root_relative_path_without_root_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """))
    assert e.key == "tests.skills.prompt"
    assert "SKILL.md" in e.message


def test_root_relative_include_without_root_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt:
              include: skills/**/SKILL.md
    """))
    assert e.key == "tests.skills.prompt.include"
    assert "skills/**/SKILL.md" in e.message
