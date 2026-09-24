"""`skilleval.testfile.load`: file level, test entries, `needs`, prompt forms and path resolution
as `load` applies it. Check parameters and template merging are covered elsewhere."""

from pathlib import Path

import pytest

from skilleval.testfile import FilePrompt, GlobPrompt, LoadError, TextPrompt, load

STATIC = """
    tests:
      skills:
        kind: static-check
        prompt: {text: hi}
"""
ONE = "{kind: static-check, prompt: {text: hi}}"


def load_error(path: Path) -> LoadError:
    with pytest.raises(LoadError) as info:
        load(path)
    return info.value


# File level


def test_test_file_fields(project):
    path = project.write("skills.eval.yml", "    root: pyproject.toml\n" + STATIC)
    tf = load(path)
    assert tf.path == path
    assert tf.root == project.root
    assert list(tf.tests) == ["skills"]


def test_root_is_none_without_the_key(project):
    assert load(project.write("t.eval.yml", STATIC)).root is None


def test_file_without_tests_or_templates_is_a_load_error(project):
    assert load_error(project.write("t.eval.yml", "root: pyproject.toml\n")).key == "tests"


@pytest.mark.parametrize("text", ["- a\n", "just text\n", "tests: [\n", ""], ids=["list", "scalar", "invalid yaml", "empty"])
def test_document_that_is_not_a_mapping_is_a_load_error_naming_the_file(project, text):
    path = project.write("t.eval.yml", text)
    e = load_error(path)
    assert e.key == ""
    assert str(e) == f"{path}: {e.message}"


@pytest.mark.parametrize("text, key", [
    ("tests: [skills]\n", "tests"),
    ("tests:\n  skills: static-check\n", "tests.skills"),
    ("templates:\n  tpl: [chars]\n", "templates.tpl"),
])
def test_a_section_that_is_not_a_mapping_is_a_load_error_at_its_key(project, text, key):
    assert load_error(project.write("t.eval.yml", text)).key == key


@pytest.mark.parametrize("text, key, value", [
    ("    root: pyproject.toml\n    root: pyproject.toml\n" + STATIC, "root", "root"),
    (STATIC + "      skills:\n        kind: static-check\n        prompt: {text: hi}\n", "tests.skills", "skills"),
], ids=["top level", "test id"])
def test_duplicate_key_anywhere_is_a_load_error(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


@pytest.mark.parametrize("text, key, value", [
    (STATIC + "    name: Skills\n", "name", "name"),
    (STATIC + "        name: Every skill file\n", "tests.skills.name", "name"),
    (STATIC + "        setup: x\n", "tests.skills.setup", "setup"),
    ("tests:\n  skills:\n    kind: static-check\n    prompt: {text: hi, extra: 1}\n", "tests.skills.prompt.extra", "extra"),
], ids=["file", "test", "evaluation key on a static-check", "prompt"])
def test_unknown_key_is_a_load_error_at_its_location(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


# Test entries


def test_test_entry_fields_with_their_defaults(project):
    t = load(project.write("t.eval.yml", STATIC)).tests["skills"]
    assert (t.id, t.kind, t.needs, t.checks) == ("skills", "static-check", (), ())


@pytest.mark.parametrize("text, key, value", [
    ("tests:\n  skills:\n    prompt: {text: hi}\n", "tests.skills.kind", "kind"),
    ("tests:\n  skills:\n    kind: evaluation\n    prompt: {text: hi}\n", "tests.skills.kind", "evaluation"),
    ("tests:\n  skills:\n    kind: benchmark\n    prompt: {text: hi}\n", "tests.skills.kind", "benchmark"),
    ("tests:\n  skills:\n    kind: nope\n    prompt: {text: hi}\n", "tests.skills.kind", "nope"),
    ("templates:\n  tpl:\n    lint: [chars]\n", "templates.tpl.kind", "kind"),
    ("templates:\n  tpl:\n    kind: nope\n", "templates.tpl.kind", "nope"),
], ids=["missing", "evaluation not yet specified", "benchmark not yet specified", "unknown", "missing on a template", "unknown on a template"])
def test_kind_missing_or_other_than_static_check_is_a_load_error(project, text, key, value):
    path = project.write("t.eval.yml", text)
    e = load_error(path)
    assert (e.path, e.key) == (path, key)
    assert value in e.message
    assert str(e) == f"{path}: {key}: {e.message}"


@pytest.mark.parametrize("needs, expected", [("a", ("a",)), ("[a, b]", ("a", "b")), ("[]", ())])
def test_needs_is_one_id_or_a_list_kept_as_a_tuple(project, needs, expected):
    text = f"tests:\n  a: {ONE}\n  b: {ONE}\n  c: {{kind: static-check, prompt: {{text: hi}}, needs: {needs}}}\n"
    assert load(project.write("t.eval.yml", text)).tests["c"].needs == expected


@pytest.mark.parametrize("text, key, value", [
    (STATIC + "        needs: nope\n", "tests.skills.needs", "nope"),
    (f"tests:\n  a: {ONE}\n  b: {{kind: static-check, prompt: {{text: hi}}, needs: [a, nope]}}\n", "tests.b.needs[1]", "nope"),
    (STATIC + "        needs: skills\n", "tests.skills.needs", "skills"),
], ids=["unknown id", "unknown id in a list", "self"])
def test_needs_unknown_id_or_self_reference_is_a_load_error(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


def test_needs_cycle_is_a_load_error(project):
    text = "tests:\n  a: {kind: static-check, prompt: {text: hi}, needs: b}\n  b: {kind: static-check, prompt: {text: hi}, needs: a}\n"
    assert load_error(project.write("t.eval.yml", text)).key in ("tests.a.needs", "tests.b.needs")


@pytest.mark.parametrize("tests, order", [
    (f"c: {ONE}\n  a: {ONE}\n  b: {ONE}", ["c", "a", "b"]),
    (f"c: {{kind: static-check, prompt: {{text: hi}}, needs: a}}\n  a: {ONE}\n  b: {ONE}", ["a", "c", "b"]),
    (f"c: {{kind: static-check, prompt: {{text: hi}}, needs: b}}\n  b: {{kind: static-check, prompt: {{text: hi}}, needs: a}}\n  a: {ONE}", ["a", "b", "c"]),
], ids=["file order", "needed test pulled up", "chain"])
def test_tests_keep_file_order_with_a_needed_test_pulled_up_before_its_first_user(project, tests, order):
    assert list(load(project.write("t.eval.yml", f"tests:\n  {tests}\n")).tests) == order


# Prompt forms


@pytest.mark.parametrize("path, text, expected", [
    ("t.eval.yml", "root: pyproject.toml\ntests:\n  skills:\n    kind: static-check\n    prompt: skills/*.md\n", "skills/*.md"),
    ("sub/t.eval.yml", "tests:\n  skills:\n    kind: static-check\n    prompt: ./SKILL.md\n", "sub/SKILL.md"),
], ids=["root-relative, never globbed", "dot-slash, from the test file"])
def test_file_prompt_is_one_resolved_path(project, path, text, expected):
    assert load(project.write(path, text)).tests["skills"].prompt == FilePrompt(project.root / expected)


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


@pytest.mark.parametrize("dotslash, prompt, include, exclude", [
    (False, '{include: "**/SKILL.md"}', "**/SKILL.md", ()),
    (False, '{include: "**/SKILL.md", exclude: "**/fixtures/**"}', "**/SKILL.md", ("**/fixtures/**",)),
    (False, '{include: "**/SKILL.md", exclude: ["**/fixtures/**", "**/legacy/**"]}', "**/SKILL.md", ("**/fixtures/**", "**/legacy/**")),
    (True, "{include: ./skills/**/SKILL.md}", "skills/**/SKILL.md", ()),
], ids=["no exclude", "one exclude", "exclude list", "dot-slash include, based on the test file"])
def test_glob_prompt_has_a_base_an_include_and_exclude_as_a_tuple(project, dotslash, prompt, include, exclude):
    # dotslash: the test file sits in sub/ and declares no root; otherwise it is at the root and declares it
    path, head, base = ("sub/t.eval.yml", "", "sub") if dotslash else ("t.eval.yml", "root: pyproject.toml\n", ".")
    text = head + f"tests:\n  skills:\n    kind: static-check\n    prompt: {prompt}\n"
    assert load(project.write(path, text)).tests["skills"].prompt == GlobPrompt(project.root / base, include, exclude)


@pytest.mark.parametrize("prompt", [
    "prompt: [SKILL.md]", "prompt: 3", "prompt: {}", 'prompt: {exclude: "**/fixtures/**"}', "prompt: {text: hi, include: ./SKILL.md}", "",
], ids=["list", "number", "empty mapping", "exclude alone", "text and include", "missing"])
def test_prompt_missing_or_of_another_shape_is_a_load_error(project, prompt):
    e = load_error(project.write("t.eval.yml", f"tests:\n  skills:\n    kind: static-check\n    {prompt}\n"))
    assert e.key == "tests.skills.prompt"


# Root and path resolution


def test_root_marker_never_found_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "    root: no-such-marker.xyz\n"))
    assert e.key == "root"
    assert "no-such-marker.xyz" in e.message


@pytest.mark.parametrize("text, key, value", [
    ("tests:\n  skills:\n    kind: static-check\n    prompt: SKILL.md\n", "tests.skills.prompt", "SKILL.md"),
    ("tests:\n  skills:\n    kind: static-check\n    prompt:\n      include: skills/**/SKILL.md\n", "tests.skills.prompt.include", "skills/**/SKILL.md"),
    (STATIC + "        uses: shared.eval.yml#tpl\n", "tests.skills.uses", "shared.eval.yml"),
    (STATIC + "        constraints: [{contains_none: {words: lists/banned.txt}}]\n", "tests.skills.constraints[0].contains_none.words", "lists/banned.txt"),
], ids=["prompt", "include", "uses", "word list"])
def test_root_relative_path_in_a_file_without_root_is_a_load_error_at_its_key(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message
