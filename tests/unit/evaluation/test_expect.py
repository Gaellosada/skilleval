"""`skilleval.evaluation.expect.check`: the reply and the files of the workspace, checked as a
prompt is, the workspace checked by a `run` command, a `judge` block handed to who answers it, and
what the task used held to the bounds of a `usage` block."""

import os
import re
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import tree

from skilleval.evaluation.expect import check
from skilleval.evaluation.harness import HarnessError
from skilleval.evaluation.workspace import locate
from skilleval.static import CheckResult, Finding, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check, Expectation, Judge, Run, Usage

WORDS = Check("words", {"min": None, "max": 3})
FOUR_WORDS = "see utils/strings.py for details"


def nobody(judge: Judge) -> CheckResult:
    raise AssertionError(f"{judge} is asked, and no test here holds a judge")


def test_reply_checks_run_as_on_a_prompt_and_never_read_the_workspace(tmp_path: Path) -> None:
    mentions = Check("contains", {"words": ["utils/strings.py"], "occurrences": {"min": 1, "max": None}, "case_sensitive": False})
    checks = (WORDS, replace(WORDS, severity="warn"), mentions)
    checked = check((Expectation(None, checks),), FOUR_WORDS, tmp_path, nobody, seconds=0, output_tokens=0)
    assert checked == tuple(replace(run_check(c, Prompt(FOUR_WORDS)), prefix="response") for c in checks)
    assert [result.status for result in checked] == ["failed", "warned", "passed"]


@pytest.mark.parametrize("content, checks, severity, expected", [
    (FOUR_WORDS.encode(), (WORDS,), None, [("file", "passed"), ("words", "failed")]),
    (FOUR_WORDS.encode(), (), None, [("file", "passed")]),
    (None, (WORDS,), None, [("file", "failed")]),
    (None, (WORDS,), "warn", [("file", "warned")]),
    (b"\xff\xfe", (WORDS,), None, [("file", "failed")]),
], ids=["checked", "only has to exist", "missing", "missing, as a warning", "not UTF-8 text"])
def test_a_file_is_read_from_the_workspace_and_checked_only_when_it_is_there_as_text(
    tmp_path: Path, content: bytes | None, checks: tuple[Check, ...], severity: str | None, expected: list[tuple[str, str]]
) -> None:
    if content is not None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/notes.md").write_bytes(content)
    checked = check((Expectation("docs/notes.md", checks, severity),), "the reply", tmp_path, nobody, seconds=0, output_tokens=0)
    assert [(result.prefix, result.check.name, result.status) for result in checked] == [
        ("docs/notes.md", name, status) for name, status in expected
    ]
    assert all(result.findings for result in checked if result.status != "passed")


def test_a_format_checks_the_reply_or_a_file_as_an_inline_prompt_whatever_the_file_is_named(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("{}\n", encoding="utf-8")
    expect = (Expectation(None, (Check("json"),)), Expectation("notes.md", (Check("json"), Check("anthropic-claude"))))
    checked = check(expect, "Here it is: {}", tmp_path, nobody, seconds=0, output_tokens=0)
    assert [(result.prefix, result.check.name, result.status) for result in checked] == [
        ("response", "json", "failed"),
        ("notes.md", "file", "passed"), ("notes.md", "json", "passed"), ("notes.md", "anthropic-claude", "passed"),
    ]


def test_a_path_that_cannot_be_one_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    (checked,) = check((Expectation("a\0b", (WORDS,)),), "the reply", tmp_path, nobody, seconds=0, output_tokens=0)
    assert (checked.check.name, checked.status) == ("file", "failed")


# run


@pytest.fixture
def workspace() -> Path:
    """A workspace, where `locate` puts one, holding what the model left."""
    folder = locate(Path("/project/evals/a.eval.yml"), "t")
    (folder / "src").mkdir(parents=True)
    (folder / "src/slug.py").write_text("def slugify(): ...\n", encoding="utf-8")
    (folder / "NOTES.md").write_text("notes\n", encoding="utf-8")
    return folder


def ran(command: str, folder: Path, timeout: float = 600, severity: str | None = None, directory: Path = Path("/evals")) -> CheckResult:
    (checked,) = check((Run(command, directory, timeout, severity),), "the reply", folder, nobody, seconds=0, output_tokens=0)
    return checked


def failure(command: str, message: str, severity: str | None = None) -> CheckResult:
    status = "warned" if severity == "warn" else "failed"
    name = next(line.strip() for line in command.splitlines() if line.strip())
    return CheckResult(Check(name, severity=severity), status, (Finding(message),), prefix="run")


def left(folder: Path) -> set[Path]:
    """What the system's temporary directory holds besides the workspace `folder` and its folder."""
    return set(Path(tempfile.gettempdir()).rglob("*")) - {folder.parent, folder, *folder.rglob("*")}


@pytest.mark.usefixtures("bash")
@pytest.mark.parametrize("command, severity, expected", [
    ("true", None, "passed"),
    ("echo out; echo err >&2; exit 1", None, "exited with 1\n    out\n    err"),
    ("exit 1", "warn", "exited with 1"),
    ("exit 2", None, "exited with 2"),
    ("false\necho reached", None, "exited with 1"),
    ("false | true", None, "exited with 1"),
    ("echo checked\nexit 3", None, "exited with 3\n    checked"),
    ("\n  \necho checked\nexit 3", None, "exited with 3\n    checked"),
    ("  echo x\nexit 1", None, "exited with 1\n    x"),
    ("echo dying; kill -KILL $$", None, "killed by signal 9\n    dying"),
    ("(kill -PIPE $BASHPID)", None, "exited with 141"),
    ("printf 'a\\rb\\rc\\n'; exit 1", None, "exited with 1\n    c"),
    ("printf '50%%\\r     \\r'; exit 1", None, "exited with 1\n"),
    ("printf 'crlf\\r\\n'; exit 1", None, "exited with 1\n    crlf"),
    ("printf '\\xff\\n'; exit 1", None, "exited with 1\n    \ufffd"),
    ("printf 'a\\n\\n'; exit 1", None, "exited with 1\n    a\n"),
], ids=["exit 0 passes", "any other code fails, with what it printed", "a warning", "a collection error of pytest fails",
        "a line that fails stops the command", "so does a pipe that fails", "named after its first line",
        "named after its first line that is not blank", "named after it stripped",
        "killed by a signal", "a child killed by one is an exit code",
        "a line shown from its last carriage return", "a line a carriage return cleared", "a CRLF line as it is", "bytes that are not UTF-8 replaced",
        "an empty line as one"])
def test_a_command_passes_on_exit_0_and_fails_on_any_other_code_under_the_prefix_run(
    workspace: Path, command: str, severity: str | None, expected: str
) -> None:
    checked = ran(command, workspace, severity=severity)
    if expected == "passed":
        assert checked == CheckResult(Check(command), "passed", prefix="run")
    else:
        assert checked == failure(command, expected, severity)


@pytest.mark.usefixtures("bash")
def test_a_failure_ends_with_the_last_20_lines_of_stdout_and_stderr_in_order(workspace: Path) -> None:
    command = "for i in $(seq 1 25); do if [ $((i % 2)) = 0 ]; then echo line $i >&2; else echo line $i; fi; done; exit 1"
    assert ran(command, workspace) == failure(command, "exited with 1" + "".join(f"\n    line {i}" for i in range(6, 26)))


@pytest.mark.usefixtures("bash")
def test_results_follow_the_order_of_the_blocks_a_judge_block_being_what_the_judge_given_makes_of_it(workspace: Path) -> None:
    right, short = Judge("Is it right?", "YES"), Judge("Is it short?", "NO", severity="warn")
    answers = {right: CheckResult(Check("Is it right?"), "passed"),
               short: CheckResult(Check("Is it short?", severity="warn"), "warned", (Finding("answered YES, NO required: Two lines."),))}
    expect = (Expectation(None, (WORDS,)), right, Run("exit 0", Path("/evals")), short, Expectation("NOTES.md"))
    checked = check(expect, FOUR_WORDS, workspace, answers.__getitem__, seconds=0, output_tokens=0)
    assert [(result.prefix, result.check.name) for result in checked] == [
        ("response", "words"), ("judge", "Is it right?"), ("run", "exit 0"), ("judge", "Is it short?"), ("NOTES.md", "file"),
    ]
    assert (checked[1], checked[3]) == (replace(answers[right], prefix="judge"), replace(answers[short], prefix="judge"))


@pytest.mark.usefixtures("bash")
@pytest.mark.parametrize("severity", [None, "warn"], ids=["an error", "a warning too"])
def test_exit_99_is_an_error_naming_the_command_with_what_it_printed(workspace: Path, severity: str | None) -> None:
    with pytest.raises(HarnessError) as info:
        ran("echo pytest is not installed; exit 99", workspace, severity=severity)
    assert "echo pytest is not installed; exit 99" in str(info.value)
    assert str(info.value).endswith("pytest is not installed")


def test_no_bash_on_the_path_is_an_error(workspace: Path) -> None:
    with pytest.raises(HarnessError) as info:
        ran("true", workspace)
    assert str(info.value).startswith("run: true: ")
    assert "bash" in str(info.value)


@pytest.mark.usefixtures("bash")
def test_a_command_over_its_timeout_fails_and_every_process_it_started_is_killed(workspace: Path, tmp_path: Path) -> None:
    marker = tmp_path / "written late"
    command = f"echo started; (sleep 1.5; touch '{marker}') & sleep 30"
    start = time.monotonic()
    checked = ran(command, workspace, timeout=1)
    assert time.monotonic() - start < 10
    assert checked == failure(command, "ran over 1 s\n    started")
    time.sleep(max(0.0, start + 2 - time.monotonic()))
    assert not marker.exists()
    assert left(workspace) == set()


@pytest.mark.usefixtures("bash")
def test_a_process_left_running_once_the_command_exits_neither_holds_the_check_nor_outlives_it(
    workspace: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "written late"
    command = f"(trap '' TERM; sleep 0.5; touch '{marker}') & sleep 30 & echo done"  # killed, not asked to end"
    start = time.monotonic()
    assert ran(command, workspace).status == "passed"
    assert time.monotonic() - start < 2
    time.sleep(0.8)
    assert not marker.exists()


@pytest.mark.usefixtures("bash")
@pytest.mark.parametrize("code", [0, 1], ids=["passing", "failing"])
def test_a_command_runs_in_a_copy_of_the_workspace_it_leaves_as_found_and_deletes(workspace: Path, code: int) -> None:
    found = tree(workspace)
    command = f"echo new > made.txt; rm src/slug.py; echo changed >> NOTES.md; mkdir .pytest_cache; exit {code}"
    ran(command, workspace)
    assert tree(workspace) == found
    assert left(workspace) == set()


def unreadable(path: Path) -> None:
    if not path.exists():
        path.write_text("key", encoding="utf-8")
    path.chmod(0)


AS_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file of any mode")


@pytest.mark.usefixtures("bash")
@pytest.mark.parametrize("where, leave, why", [
    pytest.param("src/secret.key", unreadable, "[Errno 13] Permission denied: '{}'", marks=AS_ROOT),
    pytest.param("", unreadable, "[Errno 13] Permission denied: '{}'", marks=AS_ROOT),
    ("src/secret.key", os.mkfifo, "`{}` is a named pipe"),
], ids=["a file left unreadable", "the workspace itself left unreadable", "a named pipe"])
def test_a_workspace_that_cannot_be_copied_fails_the_check_saying_why_runs_nothing_and_leaves_no_copy(
    workspace: Path, tmp_path: Path, where: str, leave: Callable[[Path], None], why: str
) -> None:
    left_there = workspace / where
    leave(left_there)
    marker = tmp_path / "ran"
    try:
        checked = ran(f"touch '{marker}'", workspace)
    finally:
        left_there.chmod(0o700)  # so that it can be deleted
    reason = "the workspace cannot be copied: " + why.format(left_there)
    assert checked == CheckResult(Check(f"touch '{marker}'"), "failed", (Finding(reason),), prefix="run")
    assert not marker.exists()
    assert left(workspace) == set()


@pytest.mark.usefixtures("bash")
@AS_ROOT
def test_every_file_that_cannot_be_copied_is_named_in_the_finding(workspace: Path) -> None:
    locked = [workspace / "src/a.key", workspace / "src/b.key"]
    for path in locked:
        unreadable(path)
    (finding,) = ran("true", workspace).findings
    head, reasons = finding.message.split(": ", 1)
    assert head == "the workspace cannot be copied"
    assert sorted(reasons.split("; ")) == [f"[Errno 13] Permission denied: '{path}'" for path in locked]


@pytest.mark.usefixtures("bash")
@AS_ROOT
def test_a_copy_that_cannot_be_made_is_an_error_naming_the_command(workspace: Path) -> None:
    workspace.parent.chmod(0o500)
    try:
        with pytest.raises(HarnessError) as info:
            ran("true", workspace)
    finally:
        workspace.parent.chmod(0o700)
    assert str(info.value).startswith("run: true: ")


@pytest.mark.usefixtures("bash")
@AS_ROOT
def test_a_copy_that_cannot_be_deleted_is_an_error_naming_the_command(workspace: Path) -> None:
    try:
        with pytest.raises(HarnessError) as info:
            ran("chmod 500 ..", workspace)  # the folder of the workspaces: the fixture's, in a scratch temporary directory
    finally:
        workspace.parent.chmod(0o700)
    assert str(info.value).startswith("run: chmod 500 ..: ")


@pytest.mark.usefixtures("bash")
def test_the_output_is_read_from_its_last_64_kib_so_an_endless_line_is_cut(workspace: Path) -> None:
    (finding,) = ran("head -c 204800 /dev/zero | tr '\\0' a; exit 1", workspace).findings
    assert finding.message == "exited with 1\n    " + "a" * 64 * 1024


@pytest.mark.usefixtures("bash")
def test_a_command_starts_in_a_neutrally_named_folder_beside_the_workspace_holding_the_files_the_model_left(
    workspace: Path
) -> None:
    (checked,) = ran("cat src/slug.py; pwd; exit 1", workspace).findings
    _, slug, cwd = checked.message.split("\n    ")
    assert slug == "def slugify(): ..."
    assert Path(cwd) != workspace
    assert Path(cwd).parent == workspace.parent
    assert not re.search(r"skill|eval|run-|slug|test", Path(cwd).name)  # the model may read it: it says nothing


@pytest.mark.usefixtures("bash")
def test_symbolic_links_are_copied_as_links(workspace: Path, tmp_path: Path) -> None:
    (workspace / "dangling").symlink_to(workspace / "missing")
    (workspace / "outside").symlink_to(tmp_path)
    assert ran("test -L dangling; test -L outside", workspace).status == "passed"


@pytest.mark.usefixtures("bash")
def test_a_bash_that_cannot_start_is_an_error_naming_the_command_and_leaves_no_copy(workspace: Path) -> None:
    with pytest.raises(HarnessError) as info:
        ran("echo checking\n# " + "x" * 200_000, workspace)  # beyond what one argument of a program may hold
    assert str(info.value).startswith("run: echo checking: ")
    assert "Argument list too long" in str(info.value)
    assert left(workspace) == set()


@pytest.mark.usefixtures("bash")
def test_a_command_inherits_the_environment_of_the_user(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_TOKEN", "set by the user")
    assert ran('test "$PROJECT_TOKEN" = "set by the user"', workspace).status == "passed"


@pytest.mark.usefixtures("bash")
def test_a_command_is_told_the_directory_of_the_file_declaring_it(workspace: Path, tmp_path: Path) -> None:
    (checked,) = ran('echo "$SKILLEVAL_FILE_DIR"; exit 1', workspace, directory=tmp_path).findings
    assert checked.message == f"exited with 1\n    {tmp_path}"


@pytest.fixture
def typed() -> Iterator[None]:
    """Standard input holds a line, as when the user types ahead of the run."""
    read, write = os.pipe()
    os.write(write, b"typed ahead\n")
    os.close(write)
    saved = os.dup(0)
    os.dup2(read, 0)
    os.close(read)
    yield
    os.dup2(saved, 0)
    os.close(saved)


@pytest.mark.usefixtures("bash", "typed")
def test_a_command_reads_nothing_from_standard_input(workspace: Path) -> None:
    assert ran('test -z "$(cat)"', workspace, timeout=1).status == "passed"


# usage


ELSEWHERE = Path("/workspace")  # a usage block reads nothing of the workspace


@pytest.mark.parametrize("seconds, output_tokens", [(119.9, 19_999), (120, 20_000)], ids=["within both bounds", "exactly at both"])
def test_a_task_within_its_bounds_or_exactly_at_them_passes_one_check_named_usage(seconds: float, output_tokens: int) -> None:
    usage = Usage(max_seconds=120, max_output_tokens=20_000)
    checked = check((usage,), "the reply", ELSEWHERE, nobody, seconds=seconds, output_tokens=output_tokens)
    assert checked == (CheckResult(Check("usage"), "passed"),)


@pytest.mark.parametrize("bounds, seconds, output_tokens, findings", [
    ({"max_seconds": 120}, 184.12, 0, ["max_seconds: 184.2 used, above the maximum of 120"]),
    ({"max_seconds": 120}, 120.01, 0, ["max_seconds: 120.1 used, above the maximum of 120"]),
    ({"max_seconds": 0.5}, 3.0, 0, ["max_seconds: 3.0 used, above the maximum of 0.5"]),
    ({"max_output_tokens": 20_000}, 0.0, 20_001, ["max_output_tokens: 20001 used, above the maximum of 20000"]),
    ({"max_seconds": 120, "max_output_tokens": 20_000}, 184.12, 25_000,
     ["max_seconds: 184.2 used, above the maximum of 120", "max_output_tokens: 25000 used, above the maximum of 20000"]),
    ({"max_seconds": 120, "max_output_tokens": 20_000}, 60.0, 25_000, ["max_output_tokens: 25000 used, above the maximum of 20000"]),
], ids=["seconds shown to the tenth, rounded up", "never rounded down to the bound", "whole seconds shown to the tenth too",
        "output tokens", "both bounds passed, one finding each", "a bound kept has no finding"])
def test_a_bound_passed_fails_the_check_with_one_finding_for_that_bound(
    bounds: dict[str, float], seconds: float, output_tokens: int, findings: list[str]
) -> None:
    checked = check((Usage(**bounds),), "the reply", ELSEWHERE, nobody, seconds=seconds, output_tokens=output_tokens)
    assert checked == (CheckResult(Check("usage"), "failed", tuple(Finding(f) for f in findings)),)


def test_a_usage_block_at_warn_warns_instead_of_failing() -> None:
    checked = check((Usage(max_output_tokens=10, severity="warn"),), "the reply", ELSEWHERE, nobody, seconds=1, output_tokens=11)
    finding = Finding("max_output_tokens: 11 used, above the maximum of 10")
    assert checked == (CheckResult(Check("usage", severity="warn"), "warned", (finding,)),)


def test_each_usage_block_is_checked_on_its_own_where_it_is_written_among_the_blocks() -> None:
    right = Judge("Is it right?", "YES")
    expect = (Usage(max_seconds=300), Expectation(None, (WORDS,)), Usage(max_seconds=120, severity="warn"), right)
    checked = check(expect, FOUR_WORDS, ELSEWHERE, {right: CheckResult(Check("Is it right?"), "passed")}.__getitem__,
                    seconds=184.12, output_tokens=0)
    assert [(result.prefix, result.check.name, result.status) for result in checked] == [
        ("", "usage", "passed"), ("response", "words", "failed"), ("", "usage", "warned"), ("judge", "Is it right?", "passed"),
    ]
