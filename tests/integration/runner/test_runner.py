"""`skilleval.runner`: discovery, node ids, selection and `run`, per specs/cli.md and specs/README.md."""

import textwrap
from pathlib import Path

import pytest
from conftest import Project

from skilleval import runner
from skilleval.runner import CaseResult, UsageError, collect, run
from skilleval.testfile import LoadError

FILE = "evals/a.eval.yml"


def node_ids(project: Project, tests: str, *args: str) -> list[str]:
    project.tests(tests)
    return [case.node_id for case in collect(list(args) or [FILE])]


def statuses(project: Project, tests: str) -> dict[str, CaseResult]:
    """Run every case of the written file and key the results by node id."""
    project.tests(tests)
    return {r.case.node_id: r for r in run(collect([FILE]))}


CHARS = """
t:
  kind: static-check
  prompt: {file: docs/x.md}
  lint: [chars]
"""

GLOB = """
t:
  kind: static-check
  prompt:
    include: docs/*.md
  lint: [chars]
"""

GLOB_USAGE = """
t:
  kind: static-check
  prompt:
    include: docs/*.md
  constraints:
    - contains: Usage
"""


# --- discovery -----------------------------------------------------------------


def test_no_args_collects_eval_files_under_the_current_directory_recursively(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS, "evals/a.eval.yml")
    project.tests(CHARS, "evals/sub/b.eval.yaml")
    assert [c.node_id for c in collect([])] == [
        "evals/a.eval.yml::t[docs/x.md]",
        "evals/sub/b.eval.yaml::t[docs/x.md]",
    ]


def test_yml_and_yaml_files_sort_together_by_name(project: Project) -> None:
    project.write("docs/x.md", "hello")
    for name in ("c.eval.yml", "a.eval.yml", "b.eval.yaml"):
        project.tests(CHARS, f"evals/{name}")
    assert [c.node_id for c in collect(["evals"])] == [
        "evals/a.eval.yml::t[docs/x.md]",
        "evals/b.eval.yaml::t[docs/x.md]",
        "evals/c.eval.yml::t[docs/x.md]",
    ]


@pytest.mark.parametrize("directory", [".hidden", "node_modules", "venv", "site-packages"])
def test_directory_discovery_skips_dot_and_vendored_directories(project: Project, directory: str) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS, "evals/a.eval.yml")
    project.tests(CHARS, f"{directory}/b.eval.yml")
    assert [c.node_id for c in collect(["."])] == ["evals/a.eval.yml::t[docs/x.md]"]


@pytest.mark.parametrize("name", ["evals/ci.yml", "evals/other.yaml", "evals/workflows/eval.yml"])
def test_directory_discovery_ignores_other_yaml(project: Project, name: str) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    project.write(name, "on: push\n")
    assert [c.node_id for c in collect(["evals"])] == [f"{FILE}::t[docs/x.md]"]


def test_a_file_named_explicitly_is_collected_whatever_its_name(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS, "checks.yaml")
    assert [c.node_id for c in collect(["checks.yaml"])] == ["checks.yaml::t[docs/x.md]"]


def test_a_path_written_with_a_dot_slash_gets_a_normalised_node_id(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    assert [c.node_id for c in collect([f"./{FILE}"])] == [f"{FILE}::t[docs/x.md]"]


def test_a_directory_with_a_trailing_slash_or_an_absolute_path_gets_cwd_relative_node_ids(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    assert [c.node_id for c in collect(["evals/"])] == [f"{FILE}::t[docs/x.md]"]
    assert [c.node_id for c in collect([str(project.root / "evals")])] == [f"{FILE}::t[docs/x.md]"]


def test_a_missing_path_is_a_usage_error(project: Project) -> None:
    with pytest.raises(UsageError):
        collect(["evals/missing.eval.yml"])


def test_a_bad_file_raises_load_error(project: Project) -> None:
    project.write(FILE, "test:\n  t:\n    kind: static-check\n")
    with pytest.raises(LoadError):
        collect([FILE])


# --- node ids ------------------------------------------------------------------


def test_text_prompt_has_a_bare_node_id_and_no_prompt_path(project: Project) -> None:
    project.tests("t:\n  kind: static-check\n  prompt: hello\n  lint: [chars]\n")
    (case,) = collect([FILE])
    assert case.node_id == f"{FILE}::t"
    assert case.prompt_path is None


def test_single_file_prompt_case_names_the_file_the_test_and_the_path(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    (case,) = collect([FILE])
    assert case.node_id == f"{FILE}::t[docs/x.md]"
    assert case.prompt_path.resolve() == (project.root / "docs/x.md").resolve()
    assert case.file.path.resolve() == (project.root / FILE).resolve()
    assert case.test.id == "t"


def test_single_file_prompt_node_id_carries_the_path_even_when_the_file_is_missing(project: Project) -> None:
    project.tests(CHARS)
    assert [c.node_id for c in collect([FILE])] == [f"{FILE}::t[docs/x.md]"]


def test_dot_slash_prompt_is_written_relative_to_the_cwd_in_the_node_id(project: Project) -> None:
    project.write("evals/x.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt: {file: ./x.md}\n  lint: [chars]\n")
    assert [c.node_id for c in collect([FILE])] == [f"{FILE}::t[evals/x.md]"]


def test_glob_fans_out_one_case_per_match_sorted(project: Project) -> None:
    for name in ("b", "c", "a"):
        project.write(f"docs/{name}.md", "hello")
    assert node_ids(project, GLOB) == [f"{FILE}::t[docs/{n}.md]" for n in "abc"]


def test_glob_exclude_removes_matches(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/fixtures/b.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt:
        include: docs/**/*.md
        exclude: "**/fixtures/**"
      lint: [chars]
    """
    assert node_ids(project, tests) == [f"{FILE}::t[docs/a.md]"]


def test_glob_exclude_is_matched_relative_to_where_the_glob_started(project: Project) -> None:
    project.write("docs/b.md", "hello")
    project.write("docs/fixtures/b.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt:
        include: docs/**/*.md
        exclude: docs/fixtures/**
      lint: [chars]
    """
    assert node_ids(project, tests) == [f"{FILE}::t[docs/b.md]"]


def test_glob_double_star_crosses_dot_directories(project: Project) -> None:
    project.write(".claude/skills/x/SKILL.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt:
        include: "**/SKILL.md"
      lint: [chars]
    """
    assert node_ids(project, tests) == [f"{FILE}::t[.claude/skills/x/SKILL.md]"]


def test_glob_case_prompt_path_is_the_matched_file(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.tests(GLOB)
    (case,) = collect([FILE])
    assert case.prompt_path.resolve() == (project.root / "docs/a.md").resolve()


def test_include_matching_nothing_is_one_bare_case_that_errors(project: Project) -> None:
    project.tests(GLOB)
    (case,) = collect([FILE])
    assert case.node_id == f"{FILE}::t"
    assert case.prompt_path is None
    (result,) = run([case])
    assert result.status == "error"
    assert "docs/*.md" in result.reason


def test_files_come_in_argument_order(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS, "evals/a.eval.yml")
    project.tests(CHARS, "evals/b.eval.yml")
    ids = [c.node_id for c in collect(["evals/b.eval.yml", "evals/a.eval.yml"])]
    assert ids == ["evals/b.eval.yml::t[docs/x.md]", "evals/a.eval.yml::t[docs/x.md]"]


def test_a_case_named_twice_on_the_command_line_is_collected_once(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    assert [c.node_id for c in collect(["evals", FILE])] == [f"{FILE}::t[docs/x.md]"]


# --- selection -----------------------------------------------------------------


def test_a_file_named_more_than_once_is_loaded_once(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("docs/x.md", "hello")
    project.tests(ALPHA_BETA)
    loads: list[Path] = []
    load = runner.load
    monkeypatch.setattr(runner, "load", lambda path: (loads.append(path), load(path))[1])
    collect([f"{FILE}::alpha", f"{FILE}::beta", "evals"])
    assert len(loads) == 1


def test_bare_node_id_selects_every_fanned_case(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    assert node_ids(project, GLOB, f"{FILE}::t") == [f"{FILE}::t[docs/a.md]", f"{FILE}::t[docs/b.md]"]


def test_bracketed_node_id_selects_one_fanned_case(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    assert node_ids(project, GLOB, f"{FILE}::t[docs/b.md]") == [f"{FILE}::t[docs/b.md]"]


@pytest.mark.parametrize("node_id", [f"{FILE}::t", f"{FILE}::t[docs/x.md]"])
def test_single_file_prompt_is_selected_by_either_form(project: Project, node_id: str) -> None:
    project.write("docs/x.md", "hello")
    assert node_ids(project, CHARS, node_id) == [f"{FILE}::t[docs/x.md]"]


def test_brackets_on_a_nameless_case_are_a_usage_error(project: Project) -> None:
    project.tests("t:\n  kind: static-check\n  prompt: hello\n  lint: [chars]\n")
    with pytest.raises(UsageError) as info:
        collect([f"{FILE}::t[docs/x.md]"])
    assert "brackets" in str(info.value)  # not "no case is named", which invites a search for a key that cannot exist


@pytest.mark.parametrize("arg", ["evals::t", f"{FILE}::t[docs/x.md]x", f"{FILE}::[docs/x.md]"],
                         ids=["a test of a directory", "text after the brackets", "brackets alone"])
def test_a_node_id_of_another_shape_is_a_usage_error(project: Project, arg: str) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    with pytest.raises(UsageError):
        collect([arg])


def test_unknown_test_id_is_a_usage_error(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(CHARS)
    with pytest.raises(UsageError):
        collect([f"{FILE}::nope"])


def test_bracket_key_matching_nothing_is_a_usage_error(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.tests(GLOB)
    with pytest.raises(UsageError):
        collect([f"{FILE}::t[docs/nope.md]"])


ALPHA_BETA = """
alpha:
  kind: static-check
  prompt: {file: docs/x.md}
  lint: [chars]
beta:
  kind: static-check
  prompt: {file: docs/x.md}
  lint: [chars]
"""


def test_keyword_keeps_node_ids_containing_it(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(ALPHA_BETA)
    assert [c.node_id for c in collect([FILE], keyword="alph")] == [f"{FILE}::alpha[docs/x.md]"]
    assert [c.node_id for c in collect([FILE], keyword="evals")] == [
        f"{FILE}::alpha[docs/x.md]",
        f"{FILE}::beta[docs/x.md]",
    ]
    assert collect([FILE], keyword="gamma") == []


def test_keyword_is_a_plain_substring_not_a_boolean_expression(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/a or b.md", "hello")
    project.tests(ALPHA_BETA + "gamma:\n  kind: static-check\n  prompt: {file: docs/a or b.md}\n  lint: [chars]\n")
    assert collect([FILE], keyword="alpha or beta") == []
    assert [c.node_id for c in collect([FILE], keyword="a or b")] == [f"{FILE}::gamma[docs/a or b.md]"]


# --- run: statuses -------------------------------------------------------------


def test_case_with_every_check_passing_is_passed(project: Project) -> None:
    project.write("docs/x.md", "hello")
    result = statuses(project, CHARS)[f"{FILE}::t[docs/x.md]"]
    assert result.status == "passed"
    assert [c.status for c in result.checks] == ["passed"]


def test_one_failed_check_among_passing_ones_fails_the_case(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt: {file: docs/x.md}
      lint: [chars]
      constraints:
        - contains: Usage
        - words:
            max: 5
    """
    result = statuses(project, tests)[f"{FILE}::t[docs/x.md]"]
    assert result.status == "failed"
    assert [c.status for c in result.checks] == ["passed", "failed", "passed"]


def test_case_with_only_warnings_is_passed(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt: {file: docs/x.md}
      constraints:
        - contains:
            words: Usage
            severity: warn
    """
    result = statuses(project, tests)[f"{FILE}::t[docs/x.md]"]
    assert result.status == "passed"
    assert [c.status for c in result.checks] == ["warned"]


TWO_LINT = """
t:
  kind: static-check
  prompt: {file: docs/x.md}
  lint: [chars, markdown_links]
"""


def test_missing_prompt_file_is_an_error_naming_it(project: Project) -> None:
    result = statuses(project, TWO_LINT)[f"{FILE}::t[docs/x.md]"]
    assert result.status == "error"
    assert "docs/x.md" in result.reason


def test_unclosed_frontmatter_is_an_error_naming_the_fence(project: Project) -> None:
    project.write("docs/x.md", "---\nname: x\nhello\n")
    result = statuses(project, TWO_LINT)[f"{FILE}::t[docs/x.md]"]
    assert result.status == "error"
    assert "---" in result.reason


# --- run: needs ----------------------------------------------------------------


def needs(base: str) -> str:
    """A `base` test body followed by a `dependent` that needs it."""
    return textwrap.dedent(base) + textwrap.dedent("""
    dependent:
      kind: static-check
      needs: base
      prompt: {file: docs/x.md}
      lint: [chars]
    """)


BASE_USAGE = """
base:
  kind: static-check
  prompt: {file: docs/base.md}
  constraints:
    - contains: Usage
"""


def test_dependent_runs_when_its_dependency_passed(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base.md", "Usage")
    results = statuses(project, needs(BASE_USAGE))
    assert results[f"{FILE}::dependent[docs/x.md]"].status == "passed"


@pytest.mark.parametrize("base_text", ["hello", None], ids=["failed", "errored"])
def test_dependent_is_skipped_naming_the_dependency_that_did_not_pass(
    project: Project, base_text: str | None
) -> None:
    project.write("docs/x.md", "hello")
    if base_text is not None:
        project.write("docs/base.md", base_text)
    result = statuses(project, needs(BASE_USAGE))[f"{FILE}::dependent[docs/x.md]"]
    assert result.status == "skipped"
    assert "base" in result.reason
    assert result.checks == ()


def test_dependent_is_skipped_naming_a_dependency_the_selection_left_out(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base.md", "Usage")
    project.tests(needs(BASE_USAGE))
    (result,) = run(collect([f"{FILE}::dependent"]))
    assert result.status == "skipped"
    assert "base" in result.reason


def test_dependent_of_a_skipped_dependency_is_skipped_naming_it(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base.md", "hello")
    tests = textwrap.dedent(BASE_USAGE) + textwrap.dedent("""
    middle:
      kind: static-check
      needs: base
      prompt: {file: docs/x.md}
      lint: [chars]
    dependent:
      kind: static-check
      needs: middle
      prompt: {file: docs/x.md}
      lint: [chars]
    """)
    results = statuses(project, tests)
    assert results[f"{FILE}::middle[docs/x.md]"].status == "skipped"
    result = results[f"{FILE}::dependent[docs/x.md]"]
    assert result.status == "skipped"
    assert "middle" in result.reason


def test_dependent_with_a_list_of_needs_is_skipped_when_one_is_unmet(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base.md", "hello")
    tests = textwrap.dedent(BASE_USAGE) + textwrap.dedent("""
    other:
      kind: static-check
      prompt: {file: docs/x.md}
      lint: [chars]
    dependent:
      kind: static-check
      needs: [other, base]
      prompt: {file: docs/x.md}
      lint: [chars]
    """)
    results = statuses(project, tests)
    assert results[f"{FILE}::other[docs/x.md]"].status == "passed"
    result = results[f"{FILE}::dependent[docs/x.md]"]
    assert result.status == "skipped"
    assert "base" in result.reason


BASE_GLOB = """
base:
  kind: static-check
  prompt:
    include: docs/base/*.md
  constraints:
    - contains: Usage
"""


def test_fanned_dependency_passes_only_when_every_case_passed(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base/a.md", "Usage")
    project.write("docs/base/b.md", "hello")
    results = statuses(project, needs(BASE_GLOB))
    assert results[f"{FILE}::base[docs/base/a.md]"].status == "passed"
    assert results[f"{FILE}::dependent[docs/x.md]"].status == "skipped"


def test_fanned_dependency_with_every_case_passed_unblocks_the_dependent(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base/a.md", "Usage")
    project.write("docs/base/b.md", "Usage")
    results = statuses(project, needs(BASE_GLOB))
    assert results[f"{FILE}::dependent[docs/x.md]"].status == "passed"


def test_needs_touches_no_filesystem_glob_at_run_time(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base/a.md", "Usage")
    project.write("docs/base/b.md", "Usage")
    project.tests(needs(BASE_GLOB))
    cases = collect([FILE])
    monkeypatch.setattr(Path, "glob", lambda *_, **__: pytest.fail("a glob ran at run time"))
    results = {r.case.node_id: r for r in run(cases)}
    assert results[f"{FILE}::dependent[docs/x.md]"].status == "passed"


def test_a_warning_in_the_dependency_never_blocks(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/base.md", "hello")
    base = """
    base:
      kind: static-check
      prompt: {file: docs/base.md}
      constraints:
        - contains:
            words: Usage
            severity: warn
    """
    results = statuses(project, needs(base))
    assert results[f"{FILE}::base[docs/base.md]"].status == "passed"
    assert results[f"{FILE}::dependent[docs/x.md]"].status == "passed"


# --- run: exitfirst ------------------------------------------------------------


def test_exitfirst_stops_after_the_first_failure(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests(GLOB_USAGE)
    cases = collect([FILE])
    assert len(cases) == 2
    assert [r.status for r in run(cases, exitfirst=True)] == ["failed"]


def test_exitfirst_stops_after_the_first_error(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt: {file: docs/missing.md}
      lint: [chars]
    u:
      kind: static-check
      prompt: {file: docs/x.md}
      lint: [chars]
    """
    project.tests(tests)
    assert [r.status for r in run(collect([FILE]), exitfirst=True)] == ["error"]


def test_exitfirst_keeps_the_results_before_the_failure(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt: {file: docs/x.md}
      lint: [chars]
    u:
      kind: static-check
      prompt: {file: docs/x.md}
      constraints:
        - contains: Usage
    """
    project.tests(tests)
    assert [r.status for r in run(collect([FILE]), exitfirst=True)] == ["passed", "failed"]
