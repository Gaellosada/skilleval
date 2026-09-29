"""`skilleval.testfile.load`: file level, test entries, `needs`, prompt forms and path resolution
as `load` applies it. Check parameters and template merging are covered elsewhere."""

from pathlib import Path

import pytest

from skilleval.testfile import FilePrompt, GlobPrompt, LoadError, TextPrompt, load

STATIC = """
    tests:
      skills:
        kind: static-check
        prompt: hi
"""
ONE = "{kind: static-check, prompt: hi}"


def load_error(path: Path) -> LoadError:
    with pytest.raises(LoadError) as info:
        load(path)
    return info.value


# File level


@pytest.mark.parametrize("head, rooted", [("    root: pyproject.toml\n", True), ("", False)], ids=["root", "no root"])
def test_test_file_fields(project, head, rooted):
    path = project.write("skills.eval.yml", head + STATIC)
    tf = load(path)
    assert (tf.path, tf.root, list(tf.tests)) == (path, project.root if rooted else None, ["skills"])


@pytest.mark.parametrize("content, key, said", [
    (STATIC.replace("hi", "café").encode("latin-1"), "", "cannot read the file"),
    ((STATIC + "        needs: 2025-02-30\n").encode(), "tests.skills.needs", "'2025-02-30'"),
], ids=["not UTF-8", "a date that does not exist"])
def test_file_or_value_that_cannot_be_read_is_a_load_error_naming_it(project, content, key, said):
    path = project.root / "t.eval.yml"
    path.write_bytes(content)
    e = load_error(path)
    assert (e.path, e.key) == (path, key)
    assert said in e.message


def test_file_without_tests_or_templates_is_a_load_error(project):
    assert load_error(project.write("t.eval.yml", "root: pyproject.toml\n")).key == "tests"


@pytest.mark.parametrize("text", ["- a\n", "just text\n", "tests: [\n", ""], ids=["list", "scalar", "invalid yaml", "empty"])
def test_document_that_is_not_a_mapping_is_a_load_error_naming_the_file(project, text):
    path = project.write("t.eval.yml", text)
    e = load_error(path)
    assert e.key == ""
    assert str(e) == f"{path}: {e.message}"


@pytest.mark.parametrize("text", ["? [a, b]\n: c\n", "? {a: 1}\n: c\n"], ids=["a list", "a mapping"])
def test_a_key_that_is_not_a_single_value_is_a_load_error(project, text):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == ""
    assert "a key is a single value" in e.message


@pytest.mark.parametrize("text, key", [
    ("tests: [skills]\n", "tests"),
    ("tests:\n  skills: static-check\n", "tests.skills"),
    ("templates:\n  tpl: [chars]\n", "templates.tpl"),
])
def test_a_section_that_is_not_a_mapping_is_a_load_error_at_its_key(project, text, key):
    assert load_error(project.write("t.eval.yml", text)).key == key


@pytest.mark.parametrize("text, key, value", [
    ("    root: pyproject.toml\n    root: pyproject.toml\n" + STATIC, "root", "root"),
    (STATIC + "      skills:\n        kind: static-check\n        prompt: hi\n", "tests.skills", "skills"),
    (STATIC + "        prompt: hello\n", "tests.skills.prompt", "prompt"),
    ("tests:\n  t:\n    kind: evaluation\n    setup: {harness: user_local}\n    setup: {permissions: bypass}\n",
     "tests.t.setup", "setup"),
    ("tests:\n  tests: {kind: static-check, prompt: hi}\n  tests: {lint: [chars]}\n", "tests.tests", "tests"),
], ids=["top level", "test id", "test key", "a mapping below the top level", "a test named as a section"])
def test_duplicate_key_anywhere_is_a_load_error(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


def test_tests_and_templates_sections_repeat_and_join_in_file_order(project):
    path = project.write("t.eval.yml", f"""\
        root: pyproject.toml
        tests:
          a: {ONE}
        templates:
          x: {{kind: static-check, lint: [chars]}}
        tests:
          b: {{kind: static-check, prompt: hi, uses: [./t.eval.yml#x, ./t.eval.yml#y]}}
        templates:
          y: {{kind: static-check, constraints: [{{words: {{max: 5}}}}]}}
        tests:
          c: {ONE}
    """)
    tf = load(path)
    assert list(tf.tests) == ["a", "b", "c"]
    assert [check.name for check in tf.tests["b"].checks] == ["chars", "words"]


@pytest.mark.parametrize("text, key, value", [
    (f"tests:\n  a: {ONE}\n  b: {ONE}\ntemplates: {{}}\ntests:\n  a: {ONE}\n", "tests.a", "a"),
    ("templates:\n  x: {kind: static-check}\ntests: {}\ntemplates:\n  x: {kind: static-check}\n", "templates.x", "x"),
    (f"tests: [a]\ntests:\n  b: {ONE}\n", "tests", "a"),
    (f"tests:\n  b: {ONE}\ntests: [a]\n", "tests", "a"),
], ids=["a test id", "a template name", "a first section that is not a mapping", "a second one"])
def test_a_name_in_two_sections_is_a_load_error_at_it(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


@pytest.mark.parametrize("text, key, value", [
    (STATIC + "    name: Skills\n", "name", "name"),
    (STATIC + "        name: Every skill file\n", "tests.skills.name", "name"),
    (STATIC + "        setup: x\n", "tests.skills.setup", "setup"),
    ("templates:\n  tpl:\n    kind: static-check\n    task: Say hi.\n", "templates.tpl.task", "task"),
    ("tests:\n  skills:\n    kind: static-check\n    prompt: {file: ./x.md, extra: 1}\n", "tests.skills.prompt.extra", "extra"),
    (STATIC + "        on: x\n", "tests.skills.True", "True"),
], ids=["file", "test", "evaluation key on a static-check", "evaluation key on its template", "prompt",
        "a key yaml reads as a bool, located as a key, not an index"])
def test_unknown_key_is_a_load_error_at_its_location(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


@pytest.mark.parametrize("key", ["prompt", "lint", "format", "constraints"])
def test_static_check_key_in_an_evaluation_is_a_load_error(project, key):
    e = load_error(project.write("t.eval.yml", f"tests:\n  t:\n    kind: evaluation\n    {key}: x\n"))
    assert e.key == f"tests.t.{key}"
    assert key in e.message


# Test entries


def test_test_entry_fields_with_their_defaults(project):
    t = load(project.write("t.eval.yml", STATIC)).tests["skills"]
    assert (t.id, t.kind, t.needs, t.checks) == ("skills", "static-check", (), ())


@pytest.mark.parametrize("text, key, value", [
    ("tests:\n  skills:\n    prompt: hi\n", "tests.skills.kind", "kind"),
    ("tests:\n  skills:\n    kind: benchmark\n    prompt: hi\n", "tests.skills.kind", "benchmark"),
    ("tests:\n  skills:\n    kind: nope\n    prompt: hi\n", "tests.skills.kind", "nope"),
    ("tests:\n  skills:\n    kind: [static-check]\n    prompt: hi\n", "tests.skills.kind", "static-check"),  # a list is not a kind, and not a crash
    ("templates:\n  tpl:\n    lint: [chars]\n", "templates.tpl.kind", "kind"),
    ("templates:\n  tpl:\n    kind: nope\n", "templates.tpl.kind", "nope"),
], ids=["missing", "benchmark not yet specified", "unknown", "a list", "missing on a template", "unknown on a template"])
def test_kind_missing_or_not_one_of_the_kinds_is_a_load_error(project, text, key, value):
    path = project.write("t.eval.yml", text)
    e = load_error(path)
    assert (e.path, e.key) == (path, key)
    assert value in e.message
    assert str(e) == f"{path}: {key}: {e.message}"


@pytest.mark.parametrize("needs, expected", [("a", ("a",)), ("[a, b]", ("a", "b")), ("[]", ())])
def test_needs_is_one_id_or_a_list_kept_as_a_tuple(project, needs, expected):
    text = f"tests:\n  a: {ONE}\n  b: {ONE}\n  c: {{kind: static-check, prompt: hi, needs: {needs}}}\n"
    assert load(project.write("t.eval.yml", text)).tests["c"].needs == expected


@pytest.mark.parametrize("text, key, value", [
    (STATIC + "        needs: nope\n", "tests.skills.needs", "nope"),
    (f"tests:\n  a: {ONE}\n  b: {{kind: static-check, prompt: hi, needs: [a, nope]}}\n", "tests.b.needs[1]", "nope"),
    (STATIC + "        needs: skills\n", "tests.skills.needs", "skills"),
], ids=["unknown id", "unknown id in a list", "self"])
def test_needs_unknown_id_or_self_reference_is_a_load_error(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message


def test_needs_cycle_is_a_load_error(project):
    text = "tests:\n  a: {kind: static-check, prompt: hi, needs: b}\n  b: {kind: static-check, prompt: hi, needs: a}\n"
    assert load_error(project.write("t.eval.yml", text)).key in ("tests.a.needs", "tests.b.needs")


@pytest.mark.parametrize("tests, order", [
    (f"c: {ONE}\n  a: {ONE}\n  b: {ONE}", ["c", "a", "b"]),
    (f"c: {{kind: static-check, prompt: hi, needs: a}}\n  a: {ONE}\n  b: {ONE}", ["a", "c", "b"]),
    (f"c: {{kind: static-check, prompt: hi, needs: b}}\n  b: {{kind: static-check, prompt: hi, needs: a}}\n  a: {ONE}", ["a", "b", "c"]),
], ids=["file order", "needed test pulled up", "chain"])
def test_tests_keep_file_order_with_a_needed_test_pulled_up_before_its_first_user(project, tests, order):
    assert list(load(project.write("t.eval.yml", f"tests:\n  {tests}\n")).tests) == order


# Prompt forms


@pytest.mark.parametrize("path, text, expected", [
    ("t.eval.yml", "root: pyproject.toml\ntests:\n  skills:\n    kind: static-check\n    prompt: {file: skills/*.md}\n", "skills/*.md"),
    ("sub/t.eval.yml", "tests:\n  skills:\n    kind: static-check\n    prompt: {file: ./SKILL.md}\n", "sub/SKILL.md"),
], ids=["root-relative, never globbed", "dot-slash, from the test file"])
def test_file_prompt_is_one_resolved_path(project, path, text, expected):
    assert load(project.write(path, text)).tests["skills"].prompt == FilePrompt(project.root / expected)


def test_string_prompt_is_the_prompt_itself(project):
    t = load(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: |
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
    "prompt: [SKILL.md]", "prompt: 3", "prompt: {}", 'prompt: {exclude: "**/fixtures/**"}', "prompt: {file: ./SKILL.md, include: ./SKILL.md}", "prompt: {file: ''}", "",
], ids=["list", "number", "empty mapping", "exclude alone", "file and include", "empty file", "missing"])
def test_prompt_missing_or_of_another_shape_is_a_load_error(project, prompt):
    e = load_error(project.write("t.eval.yml", f"tests:\n  skills:\n    kind: static-check\n    {prompt}\n"))
    assert e.key == "tests.skills.prompt"


# Root and path resolution


@pytest.mark.parametrize("marker, said", [("no-such-marker.xyz", "no-such-marker.xyz"), ('""', "not ''")], ids=["never found", "empty"])
def test_root_marker_never_found_or_empty_is_a_load_error(project, marker, said):
    e = load_error(project.write("t.eval.yml", f"    root: {marker}\n" + STATIC))
    assert e.key == "root"
    assert said in e.message


@pytest.mark.parametrize("text, key, value", [
    ("tests:\n  skills:\n    kind: static-check\n    prompt: {file: SKILL.md}\n", "tests.skills.prompt.file", "SKILL.md"),
    ("tests:\n  skills:\n    kind: static-check\n    prompt:\n      include: skills/**/SKILL.md\n", "tests.skills.prompt.include", "skills/**/SKILL.md"),
    (STATIC + "        uses: shared.eval.yml#tpl\n", "tests.skills.uses", "shared.eval.yml"),
    (STATIC + "        constraints: [{contains_none: {words: lists/banned.txt}}]\n", "tests.skills.constraints[0].contains_none.words", "lists/banned.txt"),
    ("tests:\n  skills:\n    kind: static-check\n    prompt: {file: /abs/SKILL.md}\n", "tests.skills.prompt.file", "/abs/SKILL.md"),
    ("tests:\n  skills:\n    kind: evaluation\n    setup: {harness: user_local, working_folder: fixtures}\n",
     "tests.skills.setup.working_folder", "fixtures"),
], ids=["prompt", "include", "uses", "word list", "absolute prompt", "working folder"])
def test_path_other_than_dot_slash_in_a_file_without_root_is_a_load_error_at_its_key(project, text, key, value):
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == key
    assert value in e.message
    assert "cannot read" not in e.message  # a path rule, not a read failure


@pytest.mark.parametrize("include", ['""', "./", "/abs/**"], ids=["empty", "dot-slash alone", "absolute"])
def test_include_that_cannot_be_globbed_is_a_load_error_at_its_key(project, include):
    text = f"root: pyproject.toml\ntests:\n  skills:\n    kind: static-check\n    prompt: {{include: {include}}}\n"
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == "tests.skills.prompt.include"


@pytest.mark.parametrize("section, key, value", [
    ("tests", "on", "True"), ("tests", "yes", "True"), ("tests", "1", "1"), ("tests", "null", "None"), ("templates", "on", "True"),
])
def test_test_or_template_id_that_yaml_reads_as_another_type_is_a_load_error_naming_it(project, section, key, value):
    e = load_error(project.write("t.eval.yml", f"{section}:\n  {key}: {ONE}\n"))
    assert e.key == section
    assert value in e.message


@pytest.mark.parametrize("exclude, key", [("'docs/[z-a].md'", "exclude"), ("['**/ok.md', 'docs/[z-a].md']", "exclude[1]")])
def test_exclude_glob_that_cannot_compile_is_a_load_error_at_its_key(project, exclude, key):
    text = f"root: pyproject.toml\ntests:\n  skills:\n    kind: static-check\n    prompt: {{include: '**/*.md', exclude: {exclude}}}\n"
    e = load_error(project.write("t.eval.yml", text))
    assert e.key == f"tests.skills.prompt.{key}"
    assert "[z-a]" in e.message
