"""`skilleval.cli.main`: exit codes, selection flags and output shape, per specs/cli.md."""

from __future__ import annotations

import re
import sys

import pytest
from conftest import Project

import skilleval
from skilleval.cli import main

FILE = "evals/a.eval.yml"
NODE = f"{FILE}::t[docs/x.md]"

GLOB_USAGE = """
t:
  kind: static-check
  prompt:
    include: docs/*.md
  constraints:
    - contains: Usage
"""

# One test per status, in file order: passed, failed, error, skipped.
ONE_OF_EACH = """
p:
  kind: static-check
  prompt: docs/x.md
  lint: [chars]
f:
  kind: static-check
  prompt: docs/x.md
  constraints:
    - contains: Usage
e:
  kind: static-check
  prompt: docs/missing.md
  lint: [chars]
s:
  kind: evaluation
"""


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


def test_exit_0_when_every_case_passed(project: Project) -> None:
    passing(project)
    assert project.cli(FILE)[0] == 0


def test_exit_0_with_only_warnings(project: Project) -> None:
    warning(project)
    assert project.cli(FILE)[0] == 0


def test_exit_1_with_a_failure(project: Project) -> None:
    failing(project)
    assert project.cli(FILE)[0] == 1


def test_exit_1_with_an_error_case(project: Project) -> None:
    erroring(project)
    assert project.cli(FILE)[0] == 1


def test_exit_2_when_a_collected_file_has_a_spec_error(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write(FILE, "test:\n  t:\n    kind: static-check\n")
    capsys.readouterr()
    assert main([FILE]) == 2
    captured = capsys.readouterr()
    assert FILE in captured.out + captured.err


def test_exit_2_aborts_the_whole_run(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    passing(project)
    project.write("evals/b.eval.yml", "test:\n  t:\n    kind: static-check\n")
    capsys.readouterr()
    assert main(["evals"]) == 2
    assert NODE not in capsys.readouterr().out


def test_exit_4_for_an_unknown_flag(project: Project) -> None:
    passing(project)
    assert project.cli("--bogus", FILE)[0] == 4


def test_exit_4_for_a_missing_path(project: Project) -> None:
    assert project.cli("evals/missing.eval.yml")[0] == 4


def test_exit_5_when_the_directory_holds_no_test_file(project: Project) -> None:
    project.write("evals/ci.yml", "on: push\n")
    assert project.cli("evals")[0] == 5


def test_exit_5_when_the_keyword_matches_nothing(project: Project) -> None:
    passing(project)
    assert project.cli("-k", "nothing", FILE)[0] == 5


def test_exit_3_on_an_internal_error(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    passing(project)

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    # `cli` must reach `run` through the module, so patching it is patching what `cli` calls.
    monkeypatch.setattr("skilleval.runner.run", boom)
    monkeypatch.setattr("skilleval.static.run_check", boom)
    assert project.cli(FILE)[0] == 3


# --- flags ---------------------------------------------------------------------


def test_collect_only_lists_node_ids_one_per_line_and_runs_nothing(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests(GLOB_USAGE)
    code, out = project.cli("--collect-only", FILE)
    assert code == 0
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
    assert code == 0
    assert lines(out) == [f"{FILE}::beta[docs/x.md]"]


def test_x_stops_at_the_first_failure(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests(GLOB_USAGE)
    code, out = project.cli("-x", "-v", FILE)
    assert code == 1
    assert f"{FILE}::t[docs/a.md] FAILED" in out.splitlines()
    assert "docs/b.md" not in out
    assert "1 failed" in out


def test_q_prints_no_per_case_lines_but_the_summary(project: Project) -> None:
    passing(project)
    code, out = project.cli("-q", FILE)
    assert code == 0
    assert NODE not in out
    assert "1 passed" in out


def test_q_still_prints_the_failures_section(project: Project) -> None:
    failing(project)
    code, out = project.cli("-q", FILE)
    assert code == 1
    assert f"{NODE} FAILED" in out.splitlines()
    assert re.search(r"^\s+contains: ", out, re.M)


def test_q_still_prints_the_errors_section(project: Project) -> None:
    erroring(project)
    code, out = project.cli("-q", FILE)
    assert code == 1
    assert f"{NODE} ERROR" in out.splitlines()
    assert "1 error" in out


def test_v_prints_one_status_line_per_case_and_the_summary_counts_each(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(ONE_OF_EACH)
    code, out = project.cli("-v", FILE)
    assert code == 1
    assert f"{FILE}::p[docs/x.md] PASSED" in out.splitlines()
    assert f"{FILE}::f[docs/x.md] FAILED" in out.splitlines()
    assert f"{FILE}::e[docs/missing.md] ERROR" in out.splitlines()
    assert any(line.startswith(f"{FILE}::s SKIPPED (") for line in out.splitlines())
    assert "1 passed" in out
    assert "1 failed" in out
    assert "1 error" in out
    assert "1 skipped" in out


def test_version_prints_the_package_version(project: Project) -> None:
    code, out = project.cli("--version")
    assert code == 0
    assert skilleval.__version__ in out


def test_main_without_argv_reads_sys_argv(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passing(project)
    monkeypatch.setattr(sys, "argv", ["skilleval", "--collect-only", FILE])
    capsys.readouterr()
    assert main(None) == 0
    assert lines(capsys.readouterr().out) == [NODE]


# --- output shape --------------------------------------------------------------


def test_default_output_starts_with_the_collected_count(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    project.tests("t:\n  kind: static-check\n  prompt:\n    include: docs/*.md\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == 0
    assert out.splitlines()[0] == "collected 2 cases"


def test_default_output_prints_one_progress_character_per_case_after_the_file(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.tests(ONE_OF_EACH)
    code, out = project.cli(FILE)
    assert code == 1
    assert any(line.startswith(f"{FILE} .FEs") for line in out.splitlines())


def test_failures_section_lists_the_case_and_its_findings(project: Project) -> None:
    failing(project)
    code, out = project.cli(FILE)
    assert code == 1
    assert f"{NODE} FAILED" in out.splitlines()
    assert re.search(r"^\s+contains: \S", out, re.M)
    assert "1 failed" in out


def test_a_finding_with_a_line_prints_it(project: Project) -> None:
    project.write("docs/x.md", "hello\nno\u00a0break\n")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == 1
    assert re.search(r"^\s+chars: .*\(line 2\)", out, re.M)


def test_a_warned_check_prints_warn_under_a_passed_case(project: Project) -> None:
    warning(project)
    code, out = project.cli("-v", FILE)
    assert code == 0
    assert f"{NODE} PASSED" in out.splitlines()
    assert re.search(r"^\s+contains: .*\[warn\]$", out, re.M)
    assert "1 warning" in out


def test_summary_counts_one_warning_per_warned_entry_per_case(project: Project) -> None:
    project.write("docs/a.md", "hello")
    project.write("docs/b.md", "hello")
    tests = """
    t:
      kind: static-check
      prompt:
        include: docs/*.md
      constraints:
        - contains:
            words: Usage
            severity: warn
        - contains:
            words: Examples
            severity: warn
    """
    project.tests(tests)
    code, out = project.cli(FILE)
    assert code == 0
    assert "4 warnings" in out
    assert "2 passed" in out


def test_errors_section_says_how_many_checks_were_skipped(project: Project) -> None:
    erroring(project)
    code, out = project.cli(FILE)
    assert code == 1
    assert f"{NODE} ERROR" in out.splitlines()
    assert "2 checks skipped" in out
    assert "1 error" in out


def test_include_matching_nothing_is_an_error_under_the_bare_node_id(project: Project) -> None:
    project.tests("t:\n  kind: static-check\n  prompt:\n    include: docs/*.md\n  lint: [chars]\n")
    code, out = project.cli(FILE)
    assert code == 1
    assert f"{FILE}::t ERROR" in out.splitlines()


def test_detected_items_print_only_in_verbose_mode(project: Project) -> None:
    project.write("docs/x.md", "See ./ref.md for details\n")
    project.tests("t:\n  kind: static-check\n  prompt: docs/x.md\n  constraints:\n    - paths:\n        style: posix\n")
    code, quiet = project.cli(FILE)
    assert code == 0
    assert "./ref.md" not in quiet
    code, verbose = project.cli("-v", FILE)
    assert code == 0
    assert "./ref.md" in verbose
