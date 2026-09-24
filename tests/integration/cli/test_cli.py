"""`skilleval.cli.main`: exit codes, selection flags and output shape, per specs/cli.md."""

import importlib.metadata
import re
import sys
from enum import IntEnum
from pathlib import Path

import pytest
from conftest import Project

import skilleval.static
from skilleval import ExitCode, main

HERE = Path(__file__).parent
FILE = "evals/a.eval.yml"
NODE = f"{FILE}::t[docs/x.md]"
FLAGS = pytest.mark.parametrize("flags", [(), ("-q",)], ids=["default", "quiet"])

GLOB_USAGE = """
t:
  kind: static-check
  prompt:
    include: docs/*.md
  constraints:
    - contains: Usage
"""


def fixture(project: Project, name: str) -> None:
    """Install `<name>.eval.yml` from this folder as the project's test file."""
    project.write(FILE, (HERE / f"{name}.eval.yml").read_text(encoding="utf-8"))


def passing(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  lint: [chars]\n")


def failing(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  constraints:\n    - contains: Usage\n")


def erroring(project: Project) -> None:
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  lint: [chars, markdown_links]\n")


def warning(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt: docs/x.md
      constraints:
        - contains:
            words: Usage
            severity: warn
    """
    project.tests(tests)


def lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if "::" in line]


# --- exit codes ----------------------------------------------------------------


def test_exit_code_is_an_int_enum_with_pytests_six_values() -> None:
    # passes against the skeleton by design: it pins values that already exist
    assert issubclass(ExitCode, IntEnum)
    assert {m.name: m.value for m in ExitCode} == {
        "OK": 0,
        "TESTS_FAILED": 1,
        "LOAD_ERROR": 2,
        "INTERNAL_ERROR": 3,
        "USAGE_ERROR": 4,
        "NO_TESTS_COLLECTED": 5,
    }


def test_exit_0_when_every_case_passed(project: Project) -> None:
    passing(project)
    assert project.cli(FILE)[0] == ExitCode.OK


def test_exit_0_with_only_warnings(project: Project) -> None:
    warning(project)
    assert project.cli(FILE)[0] == ExitCode.OK


def test_exit_1_with_a_failure(project: Project) -> None:
    failing(project)
    assert project.cli(FILE)[0] == ExitCode.TESTS_FAILED


def test_exit_1_with_an_error_case(project: Project) -> None:
    erroring(project)
    assert project.cli(FILE)[0] == ExitCode.TESTS_FAILED


def test_exit_2_when_a_collected_file_has_a_load_error(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write(FILE, "tests:\n  t:\n    kind: evaluation\n")
    capsys.readouterr()
    assert main([FILE]) == ExitCode.LOAD_ERROR
    captured = capsys.readouterr()
    assert FILE in captured.out + captured.err


def test_exit_2_aborts_the_whole_run(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    passing(project)
    project.write("evals/b.eval.yml", "test:\n  t:\n    kind: static-check\n")
    capsys.readouterr()
    assert main(["evals"]) == ExitCode.LOAD_ERROR
    assert NODE not in capsys.readouterr().out


def test_collect_only_exits_2_on_a_load_error(project: Project) -> None:
    project.write(FILE, "test:\n  t:\n    kind: static-check\n")
    assert project.cli("--collect-only", FILE)[0] == ExitCode.LOAD_ERROR


def test_exit_4_for_an_unknown_flag(project: Project) -> None:
    passing(project)
    assert project.cli("--bogus", FILE)[0] == ExitCode.USAGE_ERROR


def test_exit_4_for_a_missing_path(project: Project) -> None:
    assert project.cli("evals/missing.eval.yml")[0] == ExitCode.USAGE_ERROR


def test_exit_5_when_the_directory_holds_no_test_file(project: Project) -> None:
    project.write("evals/ci.yml", "on: push\n")
    assert project.cli("evals")[0] == ExitCode.NO_TESTS_COLLECTED


def test_exit_5_when_the_named_file_holds_only_templates(project: Project) -> None:
    project.write(FILE, "templates:\n  tpl:\n    kind: static-check\n    lint: [chars]\n")
    assert project.cli(FILE)[0] == ExitCode.NO_TESTS_COLLECTED


def test_exit_5_when_the_keyword_matches_nothing(project: Project) -> None:
    passing(project)
    assert project.cli("-k", "nothing", FILE)[0] == ExitCode.NO_TESTS_COLLECTED


def test_exit_3_on_an_internal_error_with_the_traceback_on_stderr(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passing(project)

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setitem(skilleval.static.CHECKS, "chars", boom)
    capsys.readouterr()
    assert main([FILE]) == ExitCode.INTERNAL_ERROR
    assert "RuntimeError" in capsys.readouterr().err


# --- flags ---------------------------------------------------------------------


def test_collect_only_lists_node_ids_one_per_line_and_runs_nothing(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests(GLOB_USAGE)
    code, out = project.cli("--collect-only", FILE)
    assert code == ExitCode.OK
    assert lines(out) == [f"{FILE}::t[docs/a.md]", f"{FILE}::t[docs/b.md]"]
    assert "FAILED" not in out


def test_keyword_filters_the_collected_cases(project: Project) -> None:
    project.write("docs/x.md", "hello")
    tests = """
    alpha:
      kind: static-check
      prompt: docs/x.md
      lint: [chars]
    beta:
      kind: static-check
      prompt: docs/x.md
      lint: [chars]
    """
    project.tests(tests)
    code, out = project.cli("--collect-only", "-k", "beta", FILE)
    assert code == ExitCode.OK
    assert lines(out) == [f"{FILE}::beta[docs/x.md]"]


def test_x_stops_at_the_first_failure(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests(GLOB_USAGE)
    code, out = project.cli("-x", "-v", FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{FILE}::t[docs/a.md] FAILED" in out.splitlines()
    assert "docs/b.md" not in out
    assert "1 failed" in out


def test_q_prints_no_per_case_lines_but_the_summary(project: Project) -> None:
    passing(project)
    code, out = project.cli("-q", FILE)
    assert code == ExitCode.OK
    assert NODE not in out
    assert "1 passed" in out


def test_v_prints_one_status_line_per_case_and_the_summary_counts_each(project: Project) -> None:
    project.write("docs/x.md", "hello")
    fixture(project, "one_of_each")
    code, out = project.cli("-v", FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{FILE}::p[docs/x.md] PASSED" in out.splitlines()
    assert f"{FILE}::f[docs/x.md] FAILED" in out.splitlines()
    assert f"{FILE}::e[docs/missing.md] ERROR" in out.splitlines()
    skipped = [line for line in out.splitlines() if line.startswith(f"{FILE}::s[docs/x.md] SKIPPED (")]
    assert len(skipped) == 1
    assert "1 passed" in out
    assert "1 failed" in out
    assert "1 error" in out
    assert "1 skipped" in out


def test_version_prints_the_package_version(project: Project) -> None:
    code, out = project.cli("--version")
    assert code == ExitCode.OK
    assert importlib.metadata.version("skilleval") in out


def test_help_prints_usage(project: Project) -> None:
    code, out = project.cli("--help")
    assert code == ExitCode.OK
    assert "usage:" in out


def test_main_without_argv_reads_sys_argv(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passing(project)
    monkeypatch.setattr(sys, "argv", ["skilleval", "--collect-only", FILE])
    capsys.readouterr()
    assert main(None) == ExitCode.OK
    assert lines(capsys.readouterr().out) == [NODE]


# --- output shape --------------------------------------------------------------


def test_default_output_starts_with_the_collected_count(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt:\n    include: docs/*.md\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == ExitCode.OK
    assert out.splitlines()[0] == "collected 2 cases"


def test_default_output_prints_one_progress_character_per_case_after_the_file(project: Project) -> None:
    project.write("docs/x.md", "hello")
    fixture(project, "one_of_each")
    code, out = project.cli(FILE)
    assert code == ExitCode.TESTS_FAILED
    progress = [line.split() for line in out.splitlines() if line.startswith(f"{FILE} ")]
    assert [words[1] for words in progress] == [".FEs"]


@FLAGS
def test_failures_section_lists_the_case_and_its_findings(project: Project, flags: tuple[str, ...]) -> None:
    failing(project)
    code, out = project.cli(*flags, FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{NODE} FAILED" in out.splitlines()
    assert re.search(r"^\s+contains: \S", out, re.MULTILINE)
    assert "1 failed" in out


def test_a_finding_with_a_line_prints_it(project: Project) -> None:
    project.write("docs/x.md", "hello\nno\u00a0break\n")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == ExitCode.TESTS_FAILED
    assert re.search(r"^\s+chars: .*\(line 2\)", out, re.MULTILINE)


def test_a_warned_check_prints_warn_under_a_passed_case(project: Project) -> None:
    warning(project)
    code, out = project.cli("-v", FILE)
    assert code == ExitCode.OK
    assert f"{NODE} PASSED" in out.splitlines()
    assert re.search(r"^\s+contains: .*\[warn\]$", out, re.MULTILINE)
    assert "1 warning" in out


def test_summary_counts_one_warning_per_warned_entry_per_case(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    fixture(project, "warnings")
    code, out = project.cli(FILE)
    assert code == ExitCode.OK
    assert "4 warnings" in out
    assert "2 passed" in out


@FLAGS
def test_errors_section_says_how_many_checks_were_skipped(project: Project, flags: tuple[str, ...]) -> None:
    erroring(project)
    code, out = project.cli(*flags, FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{NODE} ERROR" in out.splitlines()
    assert "2 checks skipped" in out
    assert "1 error" in out


def test_a_prompt_path_that_is_a_directory_is_an_error_case(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt: docs\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{FILE}::t[docs] ERROR" in out.splitlines()
    assert "1 error" in out


def test_text_prompt_with_only_file_lints_passes(project: Project) -> None:
    project.tests("t:\n  kind: static-check\n  prompt: {text: hello}\n  lint: [markdown_links, paths_exist]\n")
    code, out = project.cli("-v", FILE)
    assert code == ExitCode.OK
    assert f"{FILE}::t PASSED" in out.splitlines()
    assert "1 passed" in out


def test_detected_items_print_only_in_verbose_mode(project: Project) -> None:
    project.write("docs/x.md", "See ./ref.md for details\n")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  constraints:\n    - paths:\n        style: posix\n")
    code, quiet = project.cli(FILE)
    assert code == ExitCode.OK
    assert "./ref.md" not in quiet
    code, verbose = project.cli("-v", FILE)
    assert code == ExitCode.OK
    assert "./ref.md" in verbose
