"""How `load` turns the `lint`, `format` and `constraints` keys of a static-check into `Test.checks`."""

from __future__ import annotations

import re
import textwrap

import pytest
from conftest import Project

from skilleval.testfile import Check, LoadError

HEADER = "tests:\n  t:\n    kind: static-check\n    prompt: {text: hi}\n"


def checks(project: Project, body: str, path: str = "t.eval.yml", root: bool = False) -> tuple[Check, ...]:
    """Write a one-test file whose test `t` carries the check keys in `body`, load it, return its checks."""
    head = ("root: pyproject.toml\n" if root else "") + HEADER
    project.write(path, head + textwrap.indent(textwrap.dedent(body), "    "))
    return project.load(path).tests["t"].checks


def error(project: Project, body: str, **kw: str | bool) -> LoadError:
    with pytest.raises(LoadError) as info:
        checks(project, body, **kw)
    return info.value


# Entry forms, severity, order


def test_bare_lint_names_become_checks_without_parameters(project: Project) -> None:
    assert checks(project, "lint: [chars, paths_exist]") == (Check("chars", {}, "error"), Check("paths_exist", {}, "error"))


def test_lint_block_list_keeps_file_order(project: Project) -> None:
    assert [c.name for c in checks(project, "lint:\n  - paths_exist\n  - chars")] == ["paths_exist", "chars"]


def test_lint_entry_with_a_parameter_other_than_severity_is_an_error(project: Project) -> None:
    e = error(project, "lint:\n  - chars:\n      max: 3")
    assert e.key == "tests.t.lint[0].chars.max"
    assert "max" in str(e)


def test_checks_are_lint_then_format_then_constraints_in_file_order(project: Project) -> None:
    got = checks(project, """
        constraints:
          - lines: {max: 3}
          - words: {max: 3}
        format: anthropic-skill
        lint: [paths_exist, chars]
    """)
    assert [c.name for c in got] == ["paths_exist", "chars", "anthropic-skill", "lines", "words"]


@pytest.mark.parametrize("body, severity", [
    ("constraints:\n  - words: {max: 3}", "error"),
    ("constraints:\n  - words: {max: 3, severity: error}", "error"),
    ("constraints:\n  - words: {max: 3, severity: warn}", "warn"),
    ("lint: [chars]", "error"),
    ("lint:\n  - chars: {severity: warn}", "warn"),
    ("format: anthropic-skill", "error"),
    ("format: {anthropic-skill: {severity: warn}}", "warn"),
    ("format: {anthropic-skill: {}}", "error"),
])
def test_severity_defaults_to_error_and_accepts_warn(project: Project, body: str, severity: str) -> None:
    check = checks(project, body)[0]
    assert check.severity == severity
    assert "severity" not in check.params


@pytest.mark.parametrize("body, key", [
    ("constraints:\n  - words: {max: 3, severity: fatal}", "tests.t.constraints[0].words.severity"),
    ("lint:\n  - chars: {severity: fatal}", "tests.t.lint[0].chars.severity"),
    ("format: {anthropic-skill: {severity: fatal}}", "tests.t.format.anthropic-skill.severity"),
])
def test_severity_other_than_error_or_warn_is_an_error(project: Project, body: str, key: str) -> None:
    e = error(project, body)
    assert e.key == key
    assert "fatal" in str(e)


def test_a_constraint_given_twice_stands_twice(project: Project) -> None:
    got = checks(project, "constraints:\n  - words: {max: 600}\n  - words: {max: 400, severity: warn}")
    assert got == (Check("words", {"min": None, "max": 600}), Check("words", {"min": None, "max": 400}, "warn"))


def test_a_lint_rule_given_twice_stands_twice(project: Project) -> None:
    assert [c.name for c in checks(project, "lint: [chars, chars]")] == ["chars", "chars"]


@pytest.mark.parametrize("body, key, value", [
    ("lint: [nope]", "tests.t.lint[0]", "nope"),
    ("lint: [chars, words]", "tests.t.lint[1]", "words"),
    ("lint: [anthropic-skill]", "tests.t.lint[0]", "anthropic-skill"),
    ("lint:\n  - nope: {severity: warn}", "tests.t.lint[0]", "nope"),
    ("constraints:\n  - nope: {max: 3}", "tests.t.constraints[0]", "nope"),
    ("constraints:\n  - words: {max: 3}\n  - chars", "tests.t.constraints[1]", "chars"),
    ("constraints:\n  - chars: {severity: warn}", "tests.t.constraints[0]", "chars"),
    ("format: nope", "tests.t.format", "nope"),
    ("format: chars", "tests.t.format", "chars"),
    ("format: {nope: {severity: warn}}", "tests.t.format", "nope"),
])
def test_unknown_check_name_is_an_error_at_the_entry(project: Project, body: str, key: str, value: str) -> None:
    e = error(project, body)
    assert e.key == key
    assert value in str(e).lower()


# Format


@pytest.mark.parametrize("name", ["anthropic-skill", "anthropic-claude"])
def test_bare_format_is_a_check_without_parameters(project: Project, name: str) -> None:
    assert checks(project, f"format: {name}") == (Check(name, {}, "error"),)


def test_format_with_a_parameter_other_than_severity_is_an_error(project: Project) -> None:
    e = error(project, "format: {anthropic-skill: {max: 3}}")
    assert e.key == "tests.t.format.anthropic-skill.max"
    assert "max" in str(e)


# words, lines


@pytest.mark.parametrize("name", ["words", "lines"])
@pytest.mark.parametrize("given, bound", [
    ("{max: 400}", {"min": None, "max": 400}),
    ("{min: 50}", {"min": 50, "max": None}),
    ("{min: 50, max: 600}", {"min": 50, "max": 600}),
    ("{min: 3, max: 3}", {"min": 3, "max": 3}),
    ("{min: 0}", {"min": 0, "max": None}),
    ("{max: 0}", {"min": None, "max": 0}),
])
def test_count_checks_take_min_and_max_directly(project: Project, name: str, given: str, bound: dict) -> None:
    assert checks(project, f"constraints:\n  - {name}: {given}")[0] == Check(name, bound)


@pytest.mark.parametrize("name", ["words", "lines"])
def test_count_check_without_a_bound_is_an_error(project: Project, name: str) -> None:
    assert error(project, f"constraints:\n  - {name}: {{}}").key == f"tests.t.constraints[0].{name}"


@pytest.mark.parametrize("entry, key, value", [
    ("words: {max: many}", "words.max", "many"),
    ("words: {max: true}", "words.max", "true"),
    ("lines: {min: -1}", "lines.min", "-1"),
    ("words: {max: 3, foo: 1}", "words.foo", "foo"),
    ("contains: {words: Usage, occurrences: many}", "contains.occurrences", "many"),
    ("contains: {words: Usage, occurrences: -1}", "contains.occurrences", "-1"),
    ("contains: {words: Usage, occurrences: {min: many}}", "contains.occurrences.min", "many"),
    ("contains: {words: Usage, occurrences: {max: -1}}", "contains.occurrences.max", "-1"),
    ("contains: {words: Usage, case_sensitive: maybe}", "contains.case_sensitive", "maybe"),
    ("matches: {patterns: [ok], case_sensitive: true}", "matches.case_sensitive", "case_sensitive"),
    ("paths: {count: 3}", "paths.count", "3"),
    ("paths: {count: {max: many}}", "paths.count.max", "many"),
    ("paths: {style: mac}", "paths.style", "mac"),
    ("urls: {default: maybe}", "urls.default", "maybe"),
    ("urls: {count: {max: 1}, foo: 1}", "urls.foo", "foo"),
    ("code: {default: maybe}", "code.default", "maybe"),
])
def test_bad_parameter_is_an_error_at_its_key(project: Project, entry: str, key: str, value: str) -> None:
    e = error(project, f"constraints:\n  - {entry}")
    assert e.key == f"tests.t.constraints[0].{key}"
    assert value in str(e).lower()


@pytest.mark.parametrize("entry, key", [
    ("words: {min: 5, max: 3}", "words"),
    ("lines: {min: 5, max: 3}", "lines"),
    ("contains: {words: Usage, occurrences: {min: 5, max: 3}}", "contains.occurrences"),
    ("urls: {count: {min: 5, max: 3}}", "urls.count"),
])
def test_min_above_max_is_an_error(project: Project, entry: str, key: str) -> None:
    e = error(project, f"constraints:\n  - {entry}")
    assert e.key == f"tests.t.constraints[0].{key}"
    assert "5" in str(e) and "3" in str(e)


# contains, contains_any, contains_none


@pytest.mark.parametrize("name", ["contains", "contains_any"])
def test_contains_shorthand_normalises_to_full_params(project: Project, name: str) -> None:
    expected = Check(name, {"words": ["Usage"], "case_sensitive": False, "occurrences": {"min": 1, "max": None}})
    assert checks(project, f"constraints:\n  - {name}: Usage")[0] == expected


def test_contains_none_shorthand_has_no_occurrences(project: Project) -> None:
    assert checks(project, "constraints:\n  - contains_none: TODO")[0] == Check("contains_none", {"words": ["TODO"], "case_sensitive": False})


def test_contains_shorthand_takes_a_list(project: Project) -> None:
    assert checks(project, "constraints:\n  - contains: [Usage, Examples]")[0].params["words"] == ["Usage", "Examples"]


@pytest.mark.parametrize("given, words", [
    ("Usage", ["Usage"]),
    ("[Usage, Examples]", ["Usage", "Examples"]),
    ('"unit test"', ["unit test"]),
], ids=["one", "list", "phrase"])
def test_words_key_takes_one_string_or_a_list(project: Project, given: str, words: list[str]) -> None:
    assert checks(project, f"constraints:\n  - contains:\n      words: {given}")[0].params["words"] == words


def test_a_list_entry_holding_a_slash_stays_a_word(project: Project) -> None:
    assert checks(project, "constraints:\n  - contains:\n      words: [path/to.txt]")[0].params["words"] == ["path/to.txt"]


def test_words_file_beside_the_test_file_gives_one_word_per_line_blank_lines_ignored(project: Project) -> None:
    project.write("evals/banned.txt", "foo\n\n# not a comment\nbar baz\n")
    got = checks(project, "constraints:\n  - contains_none:\n      words: ./banned.txt", path="evals/t.eval.yml")
    assert got[0].params["words"] == ["foo", "# not a comment", "bar baz"]


def test_shorthand_holding_a_slash_reads_the_file(project: Project) -> None:
    project.write("banned.txt", "foo\nbar\n")
    assert checks(project, "constraints:\n  - contains: ./banned.txt")[0].params["words"] == ["foo", "bar"]


def test_words_file_without_dot_slash_resolves_from_the_root(project: Project) -> None:
    project.write("lists/banned.txt", "foo\n")
    got = checks(project, "constraints:\n  - contains_none:\n      words: lists/banned.txt", path="evals/t.eval.yml", root=True)
    assert got[0].params["words"] == ["foo"]


def test_root_relative_words_file_in_a_file_without_root_is_an_error(project: Project) -> None:
    project.write("lists/banned.txt", "foo\n")
    e = error(project, "constraints:\n  - contains_none:\n      words: lists/banned.txt", path="evals/t.eval.yml")
    assert e.key == "tests.t.constraints[0].contains_none.words"
    assert "lists/banned.txt" in str(e)


def test_missing_words_file_is_an_error(project: Project) -> None:
    e = error(project, "constraints:\n  - contains:\n      words: ./missing.txt")
    assert e.key == "tests.t.constraints[0].contains.words"
    assert "missing.txt" in str(e)


def test_empty_word_list_is_an_error(project: Project) -> None:
    assert error(project, "constraints:\n  - contains:\n      words: []").key == "tests.t.constraints[0].contains.words"


def test_words_file_holding_only_blank_lines_is_an_error(project: Project) -> None:
    project.write("empty.txt", "\n\n")
    e = error(project, "constraints:\n  - contains:\n      words: ./empty.txt")
    assert e.key == "tests.t.constraints[0].contains.words"
    assert "empty.txt" in str(e)


@pytest.mark.parametrize("name", ["contains", "contains_any", "contains_none"])
def test_case_sensitive_is_carried(project: Project, name: str) -> None:
    got = checks(project, f"constraints:\n  - {name}:\n      words: Usage\n      case_sensitive: true")
    assert got[0].params["case_sensitive"] is True


# occurrences


def list_key(name: str) -> str:
    return "words" if name.startswith("contains") else "patterns"


@pytest.mark.parametrize("name", ["contains", "contains_any", "matches", "matches_any"])
def test_occurrences_defaults_to_at_least_one(project: Project, name: str) -> None:
    got = checks(project, f"constraints:\n  - {name}: {{{list_key(name)}: [x]}}")
    assert got[0].params["occurrences"] == {"min": 1, "max": None}


@pytest.mark.parametrize("name", ["contains", "contains_any", "matches", "matches_any"])
@pytest.mark.parametrize("given, bound", [
    ("4", {"min": 4, "max": 4}),
    ("{min: 2}", {"min": 2, "max": None}),
    ("{max: 3}", {"min": None, "max": 3}),
    ("{min: 1, max: 3}", {"min": 1, "max": 3}),
    ("{min: 2, max: 2}", {"min": 2, "max": 2}),
])
def test_occurrences_normalises_to_a_bound(project: Project, name: str, given: str, bound: dict) -> None:
    got = checks(project, f"constraints:\n  - {name}: {{{list_key(name)}: [x], occurrences: {given}}}")
    assert got[0].params["occurrences"] == bound


@pytest.mark.parametrize("name", ["contains", "contains_any", "matches", "matches_any"])
def test_empty_occurrences_mapping_is_an_error(project: Project, name: str) -> None:
    e = error(project, f"constraints:\n  - {name}: {{{list_key(name)}: [x], occurrences: {{}}}}")
    assert e.key == f"tests.t.constraints[0].{name}.occurrences"


@pytest.mark.parametrize("name", ["contains_none", "matches_none"])
def test_occurrences_on_a_none_check_is_an_error(project: Project, name: str) -> None:
    e = error(project, f"constraints:\n  - {name}: {{{list_key(name)}: [x], occurrences: {{max: 0}}}}")
    assert e.key == f"tests.t.constraints[0].{name}.occurrences"
    assert "occurrences" in str(e)


def test_matches_none_params_hold_patterns_only(project: Project) -> None:
    got = checks(project, "constraints:\n  - matches_none:\n      patterns: [TODO]")
    assert list(got[0].params) == ["patterns"]


# matches, matches_any, matches_none


def test_patterns_are_compiled_with_multiline_and_no_case_folding(project: Project) -> None:
    got = checks(project, 'constraints:\n  - matches:\n      patterns: ["^## [A-Z]", "pytest -q"]')
    patterns = got[0].params["patterns"]
    assert [p.pattern for p in patterns] == ["^## [A-Z]", "pytest -q"]
    assert all(isinstance(p, re.Pattern) and p.flags & re.MULTILINE for p in patterns)
    assert not any(p.flags & re.IGNORECASE for p in patterns)


@pytest.mark.parametrize("name", ["matches", "matches_any", "matches_none"])
def test_matches_shorthand_takes_one_pattern(project: Project, name: str) -> None:
    assert [p.pattern for p in checks(project, f"constraints:\n  - {name}: TODO")[0].params["patterns"]] == ["TODO"]


def test_patterns_key_takes_one_string(project: Project) -> None:
    got = checks(project, "constraints:\n  - matches:\n      patterns: TODO")
    assert [p.pattern for p in got[0].params["patterns"]] == ["TODO"]


def test_patterns_file_beside_the_test_file_is_compiled_line_by_line(project: Project) -> None:
    project.write("evals/pats.txt", "^## [A-Z]\n\nTODO\n")
    got = checks(project, "constraints:\n  - matches:\n      patterns: ./pats.txt", path="evals/t.eval.yml")
    assert [p.pattern for p in got[0].params["patterns"]] == ["^## [A-Z]", "TODO"]


def test_missing_patterns_file_is_an_error(project: Project) -> None:
    e = error(project, "constraints:\n  - matches:\n      patterns: ./missing.txt")
    assert e.key == "tests.t.constraints[0].matches.patterns"
    assert "missing.txt" in str(e)


def test_empty_pattern_list_is_an_error(project: Project) -> None:
    assert error(project, "constraints:\n  - matches:\n      patterns: []").key == "tests.t.constraints[0].matches.patterns"


def test_invalid_pattern_is_an_error_naming_it(project: Project) -> None:
    e = error(project, 'constraints:\n  - matches:\n      patterns: ["ok", "(unclosed"]')
    assert e.key == "tests.t.constraints[0].matches.patterns[1]"
    assert "(unclosed" in str(e)


# paths


@pytest.mark.parametrize("given", ["paths", "paths: {}"])
def test_paths_without_parameters_only_reports(project: Project, given: str) -> None:
    assert checks(project, f"constraints:\n  - {given}")[0] == Check("paths", {})


@pytest.mark.parametrize("style", ["posix", "windows"])
def test_paths_style_is_carried(project: Project, style: str) -> None:
    assert checks(project, f"constraints:\n  - paths:\n      style: {style}")[0] == Check("paths", {"style": style})


@pytest.mark.parametrize("given, expected", [
    ('"path/to/*"', ["path/to/*"]),
    ('["path/to/*", "<*>"]', ["path/to/*", "<*>"]),
])
def test_paths_except_is_always_a_list(project: Project, given: str, expected: list[str]) -> None:
    got = checks(project, f"constraints:\n  - paths:\n      count: {{max: 3}}\n      except: {given}")
    assert got[0].params == {"count": {"min": None, "max": 3}, "except": expected}


def test_paths_params_hold_only_what_was_written(project: Project) -> None:
    got = checks(project, 'constraints:\n  - paths:\n      style: posix\n      count: {min: 1}\n      except: ["<*>"]\n      severity: warn')
    assert got[0] == Check("paths", {"style": "posix", "count": {"min": 1, "max": None}, "except": ["<*>"]}, "warn")


# urls, code


@pytest.mark.parametrize("name", ["urls", "code"])
@pytest.mark.parametrize("default", ["allow", "deny"])
def test_default_alone_is_valid(project: Project, name: str, default: str) -> None:
    assert checks(project, f"constraints:\n  - {name}:\n      default: {default}")[0] == Check(name, {"default": default})


@pytest.mark.parametrize("name, given, expected", [
    ("urls", "[docs.anthropic.com, github.com]", ["docs.anthropic.com", "github.com"]),
    ("urls", "localhost", ["localhost"]),
    ("code", "[bash, not_specified]", ["bash", "not_specified"]),
    ("code", "not_specified", ["not_specified"]),
])
def test_except_with_default_is_always_a_list(project: Project, name: str, given: str, expected: list[str]) -> None:
    got = checks(project, f"constraints:\n  - {name}:\n      default: deny\n      except: {given}")
    assert got[0].params == {"default": "deny", "except": expected}


@pytest.mark.parametrize("name", ["urls", "code"])
def test_except_without_default_is_an_error(project: Project, name: str) -> None:
    e = error(project, f"constraints:\n  - {name}:\n      except: [localhost]")
    assert e.key == f"tests.t.constraints[0].{name}.except"
    assert "default" in str(e)


@pytest.mark.parametrize("name", ["paths", "urls", "code"])
def test_count_is_a_bound(project: Project, name: str) -> None:
    assert checks(project, f"constraints:\n  - {name}:\n      count: {{max: 0}}")[0].params == {"count": {"min": None, "max": 0}}


@pytest.mark.parametrize("name", ["urls", "code"])
def test_count_beside_a_host_policy(project: Project, name: str) -> None:
    got = checks(project, f"constraints:\n  - {name}:\n      default: allow\n      except: [x]\n      count: {{min: 1, max: 8}}")
    assert got[0].params == {"default": "allow", "except": ["x"], "count": {"min": 1, "max": 8}}
