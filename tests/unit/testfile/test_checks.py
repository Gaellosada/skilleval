"""How `load` turns the `lint`, `format` and `constraints` keys of a static-check into `Test.checks`.

One table per mechanism the checks share: a new check adds rows to these tables, not a block."""

import textwrap

import pytest
from conftest import Project

from skilleval.testfile import Check, LoadError

HEADER = "tests:\n  t:\n    kind: static-check\n    prompt: {text: hi}\n"
AT_LEAST_ONE = {"min": 1, "max": None}


def checks(project: Project, body: str, path: str = "t.eval.yml", root: bool = False) -> tuple[Check, ...]:
    """Write a one-test file whose test `t` carries the check keys in `body`, load it, return its checks."""
    head = ("root: pyproject.toml\n" if root else "") + HEADER
    project.write(path, head + textwrap.indent(textwrap.dedent(body), "    "))
    return project.load(path).tests["t"].checks


# Entry forms: bare names, severity, order, repeats


@pytest.mark.parametrize("body, expected", [
    ("lint: [chars, paths_exist]", (Check("chars"), Check("paths_exist"))),
    ("format: anthropic-skill", (Check("anthropic-skill"),)),
    ("format: anthropic-claude", (Check("anthropic-claude"),)),
    ("format: {anthropic-skill: {}}", (Check("anthropic-skill"),)),
])
def test_bare_lint_and_format_names_become_checks_without_parameters(project: Project, body: str, expected: tuple) -> None:
    assert checks(project, body) == expected


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
    ("constraints: [{words: {max: 3, severity: error}}]", "error"),
    ("constraints: [{words: {max: 3, severity: warn}}]", "warn"),
    ("lint: [{chars: {severity: warn}}]", "warn"),
    ("format: {anthropic-skill: {severity: warn}}", "warn"),
])
def test_severity_is_accepted_on_any_entry_and_kept_out_of_params(project: Project, body: str, severity: str) -> None:
    check = checks(project, body)[0]
    assert check.severity == severity
    assert "severity" not in check.params


def test_a_constraint_given_twice_stands_twice(project: Project) -> None:
    got = checks(project, "constraints:\n  - words: {max: 600}\n  - words: {max: 400, severity: warn}")
    assert got == (Check("words", {"min": None, "max": 600}), Check("words", {"min": None, "max": 400}, "warn"))


# Bounds: one comparator behind `words`, `lines`, `count` and `occurrences`


@pytest.mark.parametrize("entry, at, bound", [
    ("words: {max: 400}", None, {"min": None, "max": 400}),
    ("lines: {min: 50}", None, {"min": 50, "max": None}),
    ("lines: {min: 50, max: 600}", None, {"min": 50, "max": 600}),
    ("words: {min: 3, max: 3}", None, {"min": 3, "max": 3}),
    ("paths: {count: {max: 0}}", "count", {"min": None, "max": 0}),
    ("urls: {count: {min: 1}}", "count", {"min": 1, "max": None}),
    ("code: {count: {min: 2, max: 2}}", "count", {"min": 2, "max": 2}),
    ("contains: {words: [x], occurrences: 4}", "occurrences", {"min": 4, "max": 4}),
    ("contains_any: {words: [x], occurrences: {max: 3}}", "occurrences", {"min": None, "max": 3}),
    ("matches: {patterns: [x], occurrences: {min: 2}}", "occurrences", {"min": 2, "max": None}),
    ("matches_any: {patterns: [x], occurrences: {min: 1, max: 3}}", "occurrences", {"min": 1, "max": 3}),
])
def test_a_bound_normalises_to_min_and_max(project: Project, entry: str, at: str | None, bound: dict) -> None:
    params = checks(project, f"constraints:\n  - {entry}")[0].params
    assert (params[at] if at else params) == bound


# Word and pattern lists: `contains*` under `words`, `matches*` under `patterns`


@pytest.mark.parametrize("entry, params", [
    ("contains: Usage", {"words": ["Usage"], "case_sensitive": False, "occurrences": AT_LEAST_ONE}),
    ("contains_any: Usage", {"words": ["Usage"], "case_sensitive": False, "occurrences": AT_LEAST_ONE}),
    ("contains_none: TODO", {"words": ["TODO"], "case_sensitive": False}),
    ("matches: TODO", {"patterns": ["TODO"], "occurrences": AT_LEAST_ONE}),
    ("matches_any: TODO", {"patterns": ["TODO"], "occurrences": AT_LEAST_ONE}),
    ("matches_none: TODO", {"patterns": ["TODO"]}),
])
def test_shorthand_normalises_to_full_params_with_defaults(project: Project, entry: str, params: dict) -> None:
    assert checks(project, f"constraints:\n  - {entry}")[0].params == params


@pytest.mark.parametrize("entry, key, expected", [
    ("contains: {words: Usage}", "words", ["Usage"]),
    ("contains_any: {words: [Usage, Examples]}", "words", ["Usage", "Examples"]),
    ('contains_none: {words: "unit test"}', "words", ["unit test"]),
    ("contains: {words: [path/to.txt]}", "words", ["path/to.txt"]),
    ("matches_any: {patterns: TODO}", "patterns", ["TODO"]),
    ('matches: {patterns: ["^## [A-Z]", "pytest -q"]}', "patterns", ["^## [A-Z]", "pytest -q"]),
], ids=["one word", "words", "phrase", "list entry with a slash", "one pattern", "patterns as written"])
def test_words_and_patterns_normalise_to_a_list_of_strings(project: Project, entry: str, key: str, expected: list[str]) -> None:
    assert checks(project, f"constraints:\n  - {entry}")[0].params[key] == expected


@pytest.mark.parametrize("listfile, testfile, root, entry, key", [
    ("evals/banned.txt", "evals/t.eval.yml", False, "contains_none: {words: ./banned.txt}", "words"),
    ("pats.txt", "t.eval.yml", False, "matches: ./pats.txt", "patterns"),
    ("lists/banned.txt", "evals/t.eval.yml", True, "contains: {words: lists/banned.txt}", "words"),
], ids=["beside the test file", "shorthand", "from the root"])
def test_a_string_with_a_slash_names_a_file_read_one_entry_per_line(
    project: Project, listfile: str, testfile: str, root: bool, entry: str, key: str
) -> None:
    project.write(listfile, "foo\n\n# not a comment\nbar baz\n")
    got = checks(project, f"constraints:\n  - {entry}", path=testfile, root=root)
    assert got[0].params[key] == ["foo", "# not a comment", "bar baz"]


def test_case_sensitive_true_is_carried(project: Project) -> None:
    got = checks(project, "constraints:\n  - contains_none: {words: Usage, case_sensitive: true}")
    assert got[0].params == {"words": ["Usage"], "case_sensitive": True}


# `paths`: reports alone without parameters, `style`


@pytest.mark.parametrize("entry, check", [
    ("paths", Check("paths")),
    ("paths: {}", Check("paths")),
    ("paths: {style: windows}", Check("paths", {"style": "windows"})),
    ('paths: {style: posix, count: {min: 1}, except: ["<*>"], severity: warn}',
     Check("paths", {"style": "posix", "count": {"min": 1, "max": None}, "except": ["<*>"]}, "warn")),
])
def test_paths_params_hold_only_what_was_written(project: Project, entry: str, check: Check) -> None:
    assert checks(project, f"constraints:\n  - {entry}")[0] == check


# Policies: `urls` hosts and `code` languages filter alike; `except` is always a list, on `paths` too


@pytest.mark.parametrize("entry, params", [
    ("urls: {default: allow}", {"default": "allow"}),
    ("code: {default: deny}", {"default": "deny"}),
    ("urls: {default: deny, except: [docs.anthropic.com, github.com]}", {"default": "deny", "except": ["docs.anthropic.com", "github.com"]}),
    ("code: {default: allow, except: not_specified}", {"default": "allow", "except": ["not_specified"]}),
    ("code: {default: deny, except: [Bash, Not_Specified]}", {"default": "deny", "except": ["Bash", "Not_Specified"]}),
    ('paths: {except: "Path/To/*"}', {"except": ["Path/To/*"]}),
    ('paths: {except: ["path/to/*", "<*>"]}', {"except": ["path/to/*", "<*>"]}),
])
def test_default_is_kept_and_except_is_always_a_list_as_written(project: Project, entry: str, params: dict) -> None:
    assert checks(project, f"constraints:\n  - {entry}")[0].params == params


# Errors: each at its dotted key, naming the value


@pytest.mark.parametrize("body, key, value", [
    ("lint: [chars, words]", "lint[1]", "words"),
    ("lint: [chars, chars]", "lint[1]", "chars"),
    ("lint: [{chars: {max: 3}}]", "lint[0].chars.max", "max"),
    ("lint: [{chars: {severity: fatal}}]", "lint[0].chars.severity", "fatal"),
    ("format: {nope: {severity: warn}}", "format", "nope"),
    ("format: {anthropic-skill: {max: 3}}", "format.anthropic-skill.max", "max"),
    ("format: {anthropic-skill: {severity: fatal}}", "format.anthropic-skill.severity", "fatal"),
    ("constraints: [{nope: {max: 3}}]", "constraints[0]", "nope"),
    ("constraints: [{chars: {severity: warn}}]", "constraints[0]", "chars"),
    ("constraints: [{words: {max: 3, severity: fatal}}]", "constraints[0].words.severity", "fatal"),
    ("constraints: [{words: {max: 3, foo: 1}}]", "constraints[0].words.foo", "foo"),
    ("constraints: [{words: {}}]", "constraints[0].words", None),
    ("constraints: [{words: {min: 5, max: 3}}]", "constraints[0].words", None),
    ("constraints: [{words: {max: many}}]", "constraints[0].words.max", "many"),
    ("constraints: [{lines: {min: -1}}]", "constraints[0].lines.min", "-1"),
    ("constraints: [{paths: {count: 3}}]", "constraints[0].paths.count", "3"),
    ("constraints: [{urls: {count: {max: true}}}]", "constraints[0].urls.count.max", "true"),
    ("constraints: [{contains: {words: Usage, occurrences: many}}]", "constraints[0].contains.occurrences", "many"),
    ("constraints: [{contains: {words: Usage, occurrences: {min: many}}}]", "constraints[0].contains.occurrences.min", "many"),
    ("constraints: [{contains_any: {words: [x], occurrences: {}}}]", "constraints[0].contains_any.occurrences", None),
    ("constraints: [{contains_none: {words: [x], occurrences: {max: 0}}}]", "constraints[0].contains_none.occurrences", "occurrences"),
    ("constraints: [{matches_none: {patterns: [x], occurrences: 0}}]", "constraints[0].matches_none.occurrences", "occurrences"),
    ("constraints: [{contains: {words: Usage, case_sensitive: maybe}}]", "constraints[0].contains.case_sensitive", "maybe"),
    ("constraints: [{urls: {default: maybe}}]", "constraints[0].urls.default", "maybe"),
    ("constraints: [{urls: {except: [localhost]}}]", "constraints[0].urls.except", "default"),
    ("constraints: [{code: {except: bash}}]", "constraints[0].code.except", "default"),
    ("constraints: [{paths: {except: ['src/[z-a].md']}}]", "constraints[0].paths.except[0]", "src/[z-a].md"),  # a glob that cannot compile
    ("constraints: [{paths: {except: 'src/[z-a].md'}}]", "constraints[0].paths.except", "src/[z-a].md"),
    ("constraints: [{contains_none: {words: ['']}}]", "constraints[0].contains_none.words[0]", None),  # a blank entry
    ("constraints: [{contains: [Usage, ' ']}]", "constraints[0].contains.words[1]", None),
    ("constraints: [{contains: {words: []}}]", "constraints[0].contains.words", None),
    ("constraints: [{contains: {words: ./missing.txt}}]", "constraints[0].contains.words", "missing.txt"),
    ('constraints: [{matches: {patterns: [ok, "(unclosed"]}}]', "constraints[0].matches.patterns[1]", "(unclosed"),
])
def test_a_bad_entry_is_an_error_at_its_key_naming_the_value(project: Project, body: str, key: str, value: str | None) -> None:
    with pytest.raises(LoadError) as info:
        checks(project, body)
    assert info.value.key == "tests.t." + key
    assert value is None or value in info.value.message.lower()


def test_a_list_file_holding_only_blank_lines_is_an_empty_list_error(project: Project) -> None:
    project.write("empty.txt", "\n\n")
    with pytest.raises(LoadError) as info:
        checks(project, "constraints:\n  - contains: {words: ./empty.txt}")
    assert info.value.key == "tests.t.constraints[0].contains.words"
    assert "empty.txt" in info.value.message


@pytest.mark.parametrize("write, entry", [
    (False, "./missing.txt"), (True, "./bad.txt"),
], ids=["missing", "not UTF-8"])
def test_a_list_file_that_cannot_be_read_is_an_error(project: Project, write: bool, entry: str) -> None:
    if write:
        (project.root / "bad.txt").write_bytes(b"\xff\xfe")
    with pytest.raises(LoadError) as info:
        checks(project, f"constraints:\n  - contains: {{words: {entry}}}")
    assert info.value.key == "tests.t.constraints[0].contains.words"
    assert "cannot read" in info.value.message


def test_a_list_file_entry_is_stripped_and_a_bom_dropped(project: Project) -> None:
    project.write("lists/banned.txt", "\ufefffoo \n bar\t\n")
    (check,) = checks(project, "constraints: [{contains_none: {words: lists/banned.txt}}]", root=True)
    assert check.params["words"] == ["foo", "bar"]
