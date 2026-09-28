"""How `load` turns the `lint`, `format` and `constraints` keys of a static-check into `Test.checks`.

One table per mechanism the checks share: a new check adds rows to these tables, not a block.
`read_constraints` is also called directly: through `load` its key always ends in `constraints`,
so only a direct call shows that its errors are located from the key it is given."""

import textwrap
from pathlib import Path

import pytest
from conftest import Project

from skilleval.testfile import Check, LoadError
from skilleval.testfile.checks import read_constraints

HEADER = "tests:\n  t:\n    kind: static-check\n    prompt: hi\n"
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
    ("constraints: [{words: {max: 3}}]", None),
    ("constraints: [{words: {max: 3, severity: error}}]", "error"),
    ("constraints: [{words: {max: 3, severity: warn}}]", "warn"),
    ("lint: [{chars: {severity: warn}}]", "warn"),
    ("format: {anthropic-skill: {severity: warn}}", "warn"),
])
def test_severity_is_accepted_on_any_entry_and_kept_out_of_params(project: Project, body: str, severity: str | None) -> None:
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
    ("contains_none: {words: Usage, case_sensitive: true}", {"words": ["Usage"], "case_sensitive": True}),
])
def test_an_entry_normalises_to_full_params_with_defaults(project: Project, entry: str, params: dict) -> None:
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
def test_a_string_with_a_slash_names_a_file_read_one_stripped_entry_per_line_bom_dropped(
    project: Project, listfile: str, testfile: str, root: bool, entry: str, key: str
) -> None:
    project.write(listfile, "\ufefffoo \n\n# not a comment\n bar baz\t\n")
    got = checks(project, f"constraints:\n  - {entry}", path=testfile, root=root)
    assert got[0].params[key] == ["foo", "# not a comment", "bar baz"]


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
    ("lint: chars", "lint", "chars"),  # not a list
    ("lint: [nope]\nconstraints: [{nope: {}}]", "lint[0]", "nope"),  # the first in lint, format, constraints order
    ("lint: [chars, words]", "lint[1]", "words"),
    ("lint: [chars, chars]", "lint[1]", "chars"),
    ("lint: [{chars: {max: 3}}]", "lint[0].chars.max", "max"),
    ("lint: [{chars: {severity: fatal}}]", "lint[0].chars.severity", "fatal"),
    ("format: {nope: {severity: warn}}", "format", "nope"),
    ("format: {anthropic-skill: {max: 3}}", "format.anthropic-skill.max", "max"),
    ("format: {anthropic-skill: {severity: fatal}}", "format.anthropic-skill.severity", "fatal"),
    ("constraints: words", "constraints", "words"),  # not a list
    ("constraints: [{nope: {max: 3}}]", "constraints[0]", "nope"),
    ("constraints: [{words: {max: 3}, lines: {max: 3}}]", "constraints[0]", "lines"),  # two checks in one entry
    ("constraints: [{paths: }]", "constraints[0].paths", "name alone"),  # no parameters is the bare name
    ("constraints: [{words: 3}]", "constraints[0].words", "3"),
    ("constraints: [{contains: {case_sensitive: true}}]", "constraints[0].contains.words", "words"),
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
    ('constraints: [{matches: {patterns: [ok, "(unclosed"]}}]', "constraints[0].matches.patterns[1]", "(unclosed"),
])
def test_a_bad_entry_is_an_error_at_its_key_naming_the_value(project: Project, body: str, key: str, value: str | None) -> None:
    with pytest.raises(LoadError) as info:
        checks(project, body)
    assert info.value.key == "tests.t." + key
    assert value is None or value in info.value.message.lower()


@pytest.mark.parametrize("content, said", [
    (None, "cannot read './list.txt'"), (b"\xff\xfe", "cannot read './list.txt'"), (b"\n\n", "'./list.txt' holds no entries"),
], ids=["missing", "not UTF-8", "only blank lines, an empty list"])
def test_a_list_file_that_cannot_be_read_or_is_empty_is_an_error(project: Project, content: bytes | None, said: str) -> None:
    if content is not None:
        (project.root / "list.txt").write_bytes(content)
    with pytest.raises(LoadError) as info:
        checks(project, "constraints:\n  - contains: {words: ./list.txt}")
    assert info.value.key == "tests.t.constraints[0].contains.words"
    assert said in info.value.message


# `read_constraints`, called directly, at a key that is not `constraints`


@pytest.mark.parametrize("value, key", [
    ([{"words": {"max": "many"}}], "a.b[0].words.max"),
    ("words", "a.b"),  # not a list
])
def test_read_constraints_locates_an_error_from_the_key_it_is_given(value: object, key: str) -> None:
    with pytest.raises(LoadError) as info:
        read_constraints(value, path=Path("t.eval.yml"), key="a.b", resolve=Path)
    assert info.value.key == key
