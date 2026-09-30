"""`skilleval.evaluation.expect.check`: the reply and the files of the workspace, checked as a
prompt is, and the workspace checked by a `run` command."""

import os
import tempfile
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import tree

from skilleval.evaluation.expect import check
from skilleval.evaluation.harness import HarnessError
from skilleval.evaluation.workspace import locate
from skilleval.static import CheckResult, Finding, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check, Expectation, Run

WORDS = Check("words", {"min": None, "max": 3})
FOUR_WORDS = "see utils/strings.py for details"


def test_reply_checks_run_as_on_a_prompt_and_never_read_the_workspace(tmp_path: Path) -> None:
    mentions = Check("contains", {"words": ["utils/strings.py"], "occurrences": {"min": 1, "max": None}, "case_sensitive": False})
    checks = (WORDS, replace(WORDS, severity="warn"), mentions)
    checked = check((Expectation(None, checks),), FOUR_WORDS, tmp_path)
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
    checked = check((Expectation("docs/notes.md", checks, severity),), "the reply", tmp_path)
    assert [(result.prefix, result.check.name, result.status) for result in checked] == [
        ("docs/notes.md", name, status) for name, status in expected
    ]
    assert all(result.findings for result in checked if result.status != "passed")


def test_a_path_that_cannot_be_one_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    (checked,) = check((Expectation("a\0b", (WORDS,)),), "the reply", tmp_path)
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
    (checked,) = check((Run(command, directory, timeout, severity),), "the reply", folder)
    return checked


def failure(command: str, message: str, severity: str | None = None) -> CheckResult:
    status = "warned" if severity == "warn" else "failed"
    return CheckResult(Check(command.splitlines()[0], severity=severity), status, (Finding(message),), prefix="run")


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
], ids=["exit 0 passes", "any other code fails, with what it printed", "a warning", "a collection error of pytest fails",
        "a line that fails stops the command", "so does a pipe that fails", "named after its first line"])
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
def test_results_follow_the_order_of_the_blocks(workspace: Path) -> None:
    expect = (Expectation(None, (WORDS,)), Run("exit 0", Path("/evals")), Expectation("NOTES.md"))
    checked = check(expect, FOUR_WORDS, workspace)
    assert [(result.prefix, result.check.name) for result in checked] == [("response", "words"), ("run", "exit 0"), ("NOTES.md", "file")]


@pytest.mark.usefixtures("bash")
def test_exit_99_is_an_error_naming_the_command_with_what_it_printed(workspace: Path) -> None:
    with pytest.raises(HarnessError) as info:
        ran("echo pytest is not installed; exit 99", workspace)
    assert "echo pytest is not installed; exit 99" in str(info.value)
    assert str(info.value).endswith("pytest is not installed")


def test_no_bash_on_the_path_is_an_error(workspace: Path) -> None:
    with pytest.raises(HarnessError) as info:
        ran("true", workspace)
    assert "bash" in str(info.value)


@pytest.mark.usefixtures("bash")
def test_a_command_over_its_timeout_fails_and_every_process_it_started_is_killed(workspace: Path, tmp_path: Path) -> None:
    marker = tmp_path / "written late"
    command = f"echo started; (sleep 0.5; touch '{marker}') & sleep 5"
    start = time.monotonic()
    checked = ran(command, workspace, timeout=0.2)
    assert time.monotonic() - start < 2
    assert checked == failure(command, "ran over 0.2 s\n    started")
    time.sleep(0.8)
    assert not marker.exists()
    assert left(workspace) == set()


@pytest.mark.usefixtures("bash")
def test_a_process_left_running_once_the_command_exits_neither_holds_the_check_nor_outlives_it(
    workspace: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "written late"
    command = f"(sleep 0.5; touch '{marker}') & sleep 30 & echo done"
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


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file of any mode")
@pytest.mark.usefixtures("bash")
def test_a_workspace_that_cannot_be_copied_is_an_error_naming_the_command_and_leaves_no_copy(workspace: Path) -> None:
    (workspace / "secret.key").write_text("key", encoding="utf-8")
    (workspace / "secret.key").chmod(0)
    with pytest.raises(HarnessError) as info:
        ran("python -m pytest -q", workspace)
    assert "python -m pytest -q" in str(info.value)
    assert left(workspace) == set()


@pytest.mark.usefixtures("bash")
def test_a_command_starts_in_a_folder_holding_the_files_the_model_left(workspace: Path) -> None:
    (checked,) = ran("cat src/slug.py; pwd; exit 1", workspace).findings
    _, slug, cwd = checked.message.split("\n    ")
    assert slug == "def slugify(): ..."
    assert Path(cwd) != workspace


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
