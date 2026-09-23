"""`skilleval.spec.load` and `glob_to_regex`: file level, test entries, prompt forms and
path resolution. Check parameters and templates are covered elsewhere."""

from __future__ import annotations

from pathlib import Path

import pytest

from skilleval.spec import FilePrompt, GlobPrompt, SpecError, TextPrompt, glob_to_regex, load

STATIC = """
    tests:
      skills:
        kind: static-check
        prompt: {text: hi}
"""


def load_error(path: Path) -> SpecError:
    with pytest.raises(SpecError) as info:
        load(path)
    return info.value


# File level


def test_test_file_fields(project):
    path = project.write("skills.eval.yml", """
        name: Skills
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
    """)
    tf = load(path)
    assert tf.path == path
    assert tf.name == "Skills"
    assert tf.root == project.root
    assert list(tf.tests) == ["skills"]


def test_name_defaults_to_the_file_name(project):
    assert load(project.write("sub/skills.eval.yml", STATIC)).name == "skills.eval.yml"


def test_root_is_none_without_the_key(project):
    assert load(project.write("t.eval.yml", STATIC)).root is None


def test_unknown_top_level_key_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "    extra: 1\n"))
    assert e.key == "extra"
    assert "extra" in e.message


def test_file_without_tests_or_templates_is_a_load_error(project):
    assert load_error(project.write("t.eval.yml", "name: x\n")).key == "tests"


@pytest.mark.parametrize("text", ["- a\n", "a\n", "tests: [\n", ""], ids=["list", "scalar", "invalid yaml", "empty"])
def test_document_that_is_not_a_mapping_is_a_load_error_naming_the_file(project, text):
    path = project.write("t.eval.yml", text)
    assert str(load_error(path)).startswith(f"{path}: ")


@pytest.mark.parametrize("text, key, value", [
    ("""
        name: x
        name: y
        tests:
          skills:
            kind: static-check
            prompt: {text: hi}
    """, "name", "name"),
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


@pytest.mark.parametrize("kind, body", [
    ("static-check", "prompt: {text: hi}"),
    ("evaluation", ""),
    ("benchmark", ""),
])
def test_id_and_kind(project, kind, body):
    t = load(project.write("t.eval.yml", f"tests:\n  skills:\n    kind: {kind}\n    {body}\n")).tests["skills"]
    assert (t.id, t.kind) == ("skills", kind)


def test_unknown_kind_is_a_load_error_naming_path_key_and_value(project):
    path = project.write("t.eval.yml", """
        tests:
          skills:
            kind: lint
            prompt: {text: hi}
    """)
    e = load_error(path)
    assert e.path == path
    assert e.key == "tests.skills.kind"
    assert "lint" in e.message
    assert str(e) == f"{path}: tests.skills.kind: {e.message}"


def test_missing_kind_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", "tests:\n  skills:\n    prompt: {text: hi}\n"))
    assert e.key == "tests.skills.kind"


def test_name_defaults_to_the_id(project):
    assert load(project.write("t.eval.yml", STATIC)).tests["skills"].name == "skills"


def test_name_is_kept_when_given(project):
    t = load(project.write("t.eval.yml", STATIC + "        name: Every skill file\n")).tests["skills"]
    assert t.name == "Every skill file"


@pytest.mark.parametrize("key", ["extra", "setup", "tasks"])
def test_unknown_key_on_a_static_check_is_a_load_error(project, key):
    e = load_error(project.write("t.eval.yml", STATIC + f"        {key}: x\n"))
    assert e.key == f"tests.skills.{key}"
    assert key in e.message


def test_static_check_without_checks_has_none(project):
    t = load(project.write("t.eval.yml", STATIC)).tests["skills"]
    assert t.checks == ()
    assert t.raw == {}


@pytest.mark.parametrize("kind", ["evaluation", "benchmark"])
def test_evaluation_and_benchmark_keep_other_keys_untouched(project, kind):
    t = load(project.write("t.eval.yml", f"""
        tests:
          exercises:
            kind: {kind}
            name: Exercises
            setup:
              harness: claude-code
            tasks: ./tasks/*.yml
    """)).tests["exercises"]
    assert t.raw == {"setup": {"harness": "claude-code"}, "tasks": "./tasks/*.yml"}
    assert t.prompt is None
    assert t.checks == ()
    assert t.name == "Exercises"


def test_needs_one_id(project):
    t = load(project.write("t.eval.yml", STATIC + """
      exercises:
        kind: evaluation
        needs: skills
    """)).tests["exercises"]
    assert t.needs == ("skills",)


def test_needs_on_an_evaluation_does_not_land_in_raw(project):
    t = load(project.write("t.eval.yml", STATIC + """
      exercises:
        kind: evaluation
        needs: skills
    """)).tests["exercises"]
    assert t.raw == {}


def test_needs_a_list(project):
    t = load(project.write("t.eval.yml", STATIC + """
      style:
        kind: static-check
        prompt: {text: hi}
      exercises:
        kind: evaluation
        needs: [skills, style]
    """)).tests["exercises"]
    assert t.needs == ("skills", "style")


def test_needs_empty_list(project):
    assert load(project.write("t.eval.yml", STATIC + "        needs: []\n")).tests["skills"].needs == ()


def test_needs_defaults_to_none(project):
    assert load(project.write("t.eval.yml", STATIC)).tests["skills"].needs == ()


def test_needs_unknown_id_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "        needs: nope\n"))
    assert e.key == "tests.skills.needs"
    assert "nope" in e.message


def test_needs_unknown_id_in_a_list_is_keyed_by_index(project):
    e = load_error(project.write("t.eval.yml", STATIC + """
      exercises:
        kind: evaluation
        needs: [skills, nope]
    """))
    assert e.key == "tests.exercises.needs[1]"
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
          c: {kind: evaluation}
          a: {kind: evaluation}
          b: {kind: evaluation}
    """))
    assert list(tf.tests) == ["c", "a", "b"]


def test_tests_put_a_needed_test_before_the_one_needing_it(project):
    tf = load(project.write("t.eval.yml", """
        tests:
          c: {kind: evaluation, needs: a}
          a: {kind: evaluation}
          b: {kind: evaluation}
    """))
    assert list(tf.tests) == ["a", "c", "b"]


def test_tests_put_a_chain_of_needs_in_dependency_order(project):
    tf = load(project.write("t.eval.yml", """
        tests:
          c: {kind: evaluation, needs: b}
          b: {kind: evaluation, needs: a}
          a: {kind: evaluation}
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


# Path resolution


def test_dot_slash_path_is_relative_to_the_test_file(project):
    t = load(project.write("sub/t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: ./SKILL.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "sub" / "SKILL.md")


def test_other_path_is_relative_to_the_project_root(project):
    t = load(project.write("sub/t.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "SKILL.md")


def test_root_is_the_nearest_ancestor_holding_the_marker_file(project):
    project.write("sub/pyproject.toml")
    tf = load(project.write("sub/deep/t.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """))
    assert tf.root == project.root / "sub"
    assert tf.tests["skills"].prompt == FilePrompt(project.root / "sub" / "SKILL.md")


def test_root_may_be_the_test_file_own_directory(project):
    project.write("sub/pyproject.toml")
    tf = load(project.write("sub/t.eval.yml", STATIC + "    root: pyproject.toml\n"))
    assert tf.root == project.root / "sub"


def test_root_marker_may_be_a_directory(project):
    (project.root / "sub" / ".git").mkdir(parents=True)
    tf = load(project.write("sub/deep/t.eval.yml", STATIC + "    root: .git\n"))
    assert tf.root == project.root / "sub"


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


# glob_to_regex


@pytest.mark.parametrize("pattern, token, expected", [
    ("*.md", "a.md", True),
    ("*.md", "dir/a.md", False),
    ("path/to/*", "path/to/a/b.py", False),
    ("a?c", "abc", True),
    ("a?c", "a/c", False),
    ("a?c", "ac", False),
    ("[ab].md", "a.md", True),
    ("[ab].md", "c.md", False),
    ("[ab].md", "/.md", False),
    ("**", "a/b/c.md", True),
    ("**/fixtures/**", "a/b/fixtures/c.md", True),
    ("**/fixtures/**", "fixtures/c.md", True),
    ("**/fixtures/**", "a/fixturesx/c.md", False),
    ("**/SKILL.md", "SKILL.md", True),
    ("**/SKILL.md", ".claude/skills/refactor/SKILL.md", True),
    ("<*>", "<file>", True),
    ("a/**/b", "a/b", True),
    ("a.md", "a.md", True),
    ("a.md", "axmd", False),
    ("a.md", "xa.md", False),
    ("a.md", "a.mdx", False),
])
def test_glob_to_regex(pattern, token, expected):
    assert bool(glob_to_regex(pattern).search(token)) is expected
