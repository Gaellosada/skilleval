"""`skilleval.cli.main`: exit codes, flags and the output, per specs/cli.md."""

import importlib.metadata
import io
import sys
import time
from enum import IntEnum
from pathlib import Path

import pytest
from conftest import FILE, Project

import skilleval.static
from skilleval import ExitCode, main

HERE = Path(__file__).parent
PASSING = {"docs/x.md": "hello", FILE: "root: pyproject.toml\ntests:\n  t: {kind: static-check, prompt: {file: docs/x.md}, lint: [chars]}\n"}
WARNED = PASSING | {"docs/x.md": "no\u00a0break", FILE: PASSING[FILE].replace("[chars]", "[{chars: {severity: warn}}]")}
NO_PROMPT = {FILE: PASSING[FILE]}  # docs/x.md is missing: an error case
BROKEN = "test:\n  t:\n    kind: static-check\n"
PASSED = "".join(f"""
{FILE}::p[docs/p/{name}.md] PASSED
  contains: 0 occurrences of 'Usage', below the minimum of 1 [warn]
  contains: 0 occurrences of 'Examples', below the minimum of 1 [warn]
  paths: detected ./ref.md""" for name in "ab")
# What report.eval.yml prints, in blocks; {missing} is the path of the prompt that is not there.
PROGRESS = f"collected 5 cases\n\n{FILE} ..FEs\n"
X_PROGRESS = f"collected 5 cases\n\n{FILE} ..F\n"  # collected, not run
VERBOSE = f"""collected 5 cases
{PASSED}
{FILE}::f[docs/y.md] FAILED
  chars: invisible character U+00A0 (no-break space) (line 2)
{FILE}::e[docs/missing.md] ERROR
{FILE}::s[docs/x.md] SKIPPED (needs f)
"""
FAILURES = f"""
=================================== FAILURES ===================================
{FILE}::f[docs/y.md] FAILED
  chars: invisible character U+00A0 (no-break space) (line 2)
"""
ERRORS = f"""
==================================== ERRORS ====================================
{FILE}::e[docs/missing.md] ERROR
  {{missing}}: [Errno 2] No such file or directory: '{{missing}}'; 2 checks skipped
"""
SUMMARY = "\n========= 1 failed, 2 passed, 1 skipped, 1 error, 4 warnings in 0.00s ==========\n"
X_SUMMARY = "\n=================== 1 failed, 2 passed, 4 warnings in 0.00s ====================\n"
# two static checks and an evaluation, for the kind flags
KINDS = """\
root: pyproject.toml
tests:
  lint: {kind: static-check, prompt: hello, lint: [chars]}
  size: {kind: static-check, prompt: hello, constraints: [{words: {max: 5}}]}
  task: {kind: evaluation, model: claude-sonnet-5, setup: {harness: user_local}, task: Say hi.}
"""


def report(project: Project) -> None:
    """Install `report.eval.yml`, one test per status, with the files it reads."""
    for path in ("docs/x.md", "docs/p/a.md", "docs/p/b.md"):
        project.write(path, "See ./ref.md\n")
    project.write("docs/y.md", "hello\nno\u00a0break\n")
    project.write(FILE, (HERE / "report.eval.yml").read_text(encoding="utf-8"))


def test_exit_code_is_an_int_enum_with_pytests_six_values() -> None:
    assert issubclass(ExitCode, IntEnum)
    assert {m.name: m.value for m in ExitCode} == dict(
        OK=0, TESTS_FAILED=1, LOAD_ERROR=2, INTERNAL_ERROR=3, USAGE_ERROR=4, NO_TESTS_COLLECTED=5
    )


@pytest.mark.parametrize("flags, printed", [
    ((), PROGRESS + FAILURES + ERRORS + SUMMARY),
    (("-v",), VERBOSE + FAILURES + ERRORS + SUMMARY),
    (("-q",), FAILURES + ERRORS + SUMMARY),
    (("-x", "-q"), FAILURES + X_SUMMARY),
    (("-x",), X_PROGRESS + FAILURES + X_SUMMARY),
], ids=["default", "verbose", "quiet", "exitfirst", "exitfirst counting what was collected"])
def test_output_has_pytests_shape(project: Project, monkeypatch: pytest.MonkeyPatch, flags: tuple[str, ...], printed: str) -> None:
    report(project)
    monkeypatch.setattr(time, "perf_counter", lambda: 0.0)
    expected = printed.format(missing=project.root / "docs/missing.md")
    assert project.cli(*flags, FILE) == (ExitCode.TESTS_FAILED, expected)


class Terminal(io.StringIO):
    """Standard output that keeps what it held when it was last flushed."""

    flushed = ""

    def flush(self) -> None:
        self.flushed = self.getvalue()


@pytest.mark.parametrize("flags, marks, head", [
    ((), ["evals/a.eval.yml ", "evals/a.eval.yml .", "evals/b.eval.yml "],
     "collected 3 cases\n\nevals/a.eval.yml .F\nevals/b.eval.yml .\n\n===="),
    (("-v",), ["evals/a.eval.yml::t ", "evals/a.eval.yml::u ", "evals/b.eval.yml::v "],
     "collected 3 cases\n\nevals/a.eval.yml::t PASSED\nevals/a.eval.yml::u FAILED\n  chars: "),
    (("-q",), ["", "", ""], "\n===="),
], ids=["a progress character per case", "a line per case", "nothing until the end"])
def test_the_report_is_printed_and_flushed_as_the_cases_run(
    project: Project, monkeypatch: pytest.MonkeyPatch, flags: tuple[str, ...], marks: list[str], head: str
) -> None:
    project.write("evals/a.eval.yml", 'root: pyproject.toml\ntests:\n  t: {kind: static-check, prompt: hello, lint: [chars]}\n'
                  '  u: {kind: static-check, prompt: "no\\u00a0break", lint: [chars]}\n')
    project.write("evals/b.eval.yml", "root: pyproject.toml\ntests:\n  v: {kind: static-check, prompt: hello, lint: [chars]}\n")
    terminal, chars, seen = Terminal(), skilleval.static.CHECKS["chars"], []
    monkeypatch.setitem(skilleval.static.CHECKS, "chars", lambda *args: seen.append(terminal.flushed) or chars(*args))
    monkeypatch.setattr(sys, "stdout", terminal)
    monkeypatch.setattr(time, "perf_counter", lambda: 0.0)
    assert main([*flags, "evals"]) == ExitCode.TESTS_FAILED
    out = terminal.getvalue()
    assert seen == [out[:out.index(mark) + len(mark)] if mark else "" for mark in marks]  # each case starts on its head
    assert terminal.flushed == out
    assert out.startswith(head)


@pytest.mark.parametrize("files, args, code, said", [
    (PASSING, [FILE], ExitCode.OK, None),
    (PASSING, [FILE, "-k", "nothing"], ExitCode.NO_TESTS_COLLECTED, None),
    (WARNED, [FILE], ExitCode.OK, None),
    (NO_PROMPT, [FILE], ExitCode.TESTS_FAILED, None),
    ({FILE: "tests:\n  t:\n    kind: benchmark\n"}, [FILE], ExitCode.LOAD_ERROR, FILE),
    (PASSING | {"evals/b.eval.yml": BROKEN}, ["evals"], ExitCode.LOAD_ERROR, "evals/b.eval.yml"),
    ({FILE: BROKEN}, ["--collect-only", FILE], ExitCode.LOAD_ERROR, FILE),
    (PASSING, ["--bogus", FILE], ExitCode.USAGE_ERROR, "--bogus"),
    (PASSING, ["-q", "-v", FILE], ExitCode.USAGE_ERROR, "not allowed with"),
    (PASSING, ["--static-checks", "--evaluations", FILE], ExitCode.USAGE_ERROR, "not allowed with"),
    (PASSING, ["--evaluations", f"{FILE}::t"], ExitCode.NO_TESTS_COLLECTED, None),
    ({FILE: KINDS}, ["--static-checks", FILE], ExitCode.OK, None),
    ({}, ["evals/missing.eval.yml"], ExitCode.USAGE_ERROR, "evals/missing.eval.yml"),
    ({"evals/ci.yml": "on: push\n"}, ["evals"], ExitCode.NO_TESTS_COLLECTED, None),
    ({FILE: "templates:\n  tpl:\n    kind: static-check\n    lint: [chars]\n"}, [FILE], ExitCode.NO_TESTS_COLLECTED, None),
], ids=["every case passed", "a keyword matching nothing", "only warnings", "an error case", "a load error",
        "a load error in any file aborts the run", "a load error on collect-only", "an unknown flag", "-q with -v",
        "both kind flags", "a kind flag keeping nothing", "a kind flag running only its kind", "a missing path",
        "no test file", "only templates"])
def test_exit_code_says_how_the_run_went(
    project: Project, capsys: pytest.CaptureFixture[str], files: dict[str, str], args: list[str], code: ExitCode, said: str | None
) -> None:
    for path, text in files.items():
        project.write(path, text)
    capsys.readouterr()
    assert main(args) == code
    out, err = capsys.readouterr()
    assert said is None or said in err  # why it stopped, when it did
    if code > ExitCode.TESTS_FAILED:
        assert "passed" not in out  # nothing ran


def test_an_internal_error_exits_3_ending_the_open_line_before_the_traceback(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report(project)
    monkeypatch.setitem(skilleval.static.CHECKS, "chars", lambda *args: 1 / 0)
    capsys.readouterr()
    assert main([FILE]) == ExitCode.INTERNAL_ERROR
    out, err = capsys.readouterr()
    assert out == f"collected 5 cases\n\n{FILE} ..\n"  # the progress line it left open ended
    assert "ZeroDivisionError" in err


@pytest.mark.parametrize("flags, printed", [
    ((), f"collected 5 cases\n\n{FILE} ..\n"),
    (("-v",), f"collected 5 cases\n{PASSED}\n{FILE}::f[docs/y.md] \n"),
    (("-q",), ""),
], ids=["the progress line ended", "the case line ended", "nothing at -q"])
def test_ctrl_c_ends_the_progress_line_it_left_open_and_goes_on(
    project: Project, monkeypatch: pytest.MonkeyPatch, flags: tuple[str, ...], printed: str
) -> None:
    report(project)

    def interrupt(*args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setitem(skilleval.static.CHECKS, "chars", interrupt)
    monkeypatch.setattr(sys, "stdout", terminal := Terminal())
    with pytest.raises(KeyboardInterrupt):
        main([*flags, FILE])
    assert terminal.flushed == terminal.getvalue() == printed  # flushed before the traceback


@pytest.mark.parametrize("args, listed", [
    (["--collect-only"], ["p[docs/p/a.md]", "p[docs/p/b.md]", "f[docs/y.md]", "e[docs/missing.md]", "s[docs/x.md]"]),
    (["--collect-only", "-k", "missing"], ["e[docs/missing.md]"]),
])
def test_collect_only_lists_the_node_ids_kept_and_runs_nothing(project: Project, args: list[str], listed: list[str]) -> None:
    report(project)
    assert project.cli(*args, FILE) == (ExitCode.OK, "".join(f"{FILE}::{node}\n" for node in listed))


@pytest.mark.parametrize("args, listed", [
    (["--static-checks"], ["lint", "size"]),
    (["--evaluations"], ["task"]),
    (["--static-checks", "-k", "t"], ["lint"]),
    (["--evaluations", f"{FILE}::task", f"{FILE}::lint"], ["task"]),
], ids=["static checks", "evaluations", "with -k", "with node ids"])
def test_a_kind_flag_keeps_that_kind_among_what_the_arguments_and_k_select(
    project: Project, args: list[str], listed: list[str]
) -> None:
    project.write(FILE, KINDS)
    assert project.cli("--collect-only", *args) == (ExitCode.OK, "".join(f"{FILE}::{test}\n" for test in listed))


@pytest.mark.parametrize("flag, said", [("--version", f"skilleval {importlib.metadata.version('skilleval')}"), ("--help", "usage:")])
def test_version_and_help_print_and_exit_0(project: Project, flag: str, said: str) -> None:
    code, out = project.cli(flag)
    assert code == ExitCode.OK
    assert said in out


def test_main_without_argv_reads_sys_argv(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report(project)
    monkeypatch.setattr(sys, "argv", ["skilleval", "--collect-only", "-k", "missing", FILE])
    capsys.readouterr()
    assert main(None) == ExitCode.OK
    assert capsys.readouterr().out == f"{FILE}::e[docs/missing.md]\n"
