"""An evaluation through `collect`, `run` and `main`, with `Harness` in place of the harness: the
chain of tasks, what fails or stops it, the workspace, the results kept and the report.
Specified in specs/evaluations.md."""

import math
import shutil
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import FILE, Project, tree

from skilleval import ExitCode
from skilleval.evaluation.config import Config
from skilleval.evaluation.harness import HarnessError, Reply
from skilleval.evaluation.workspace import locate
from skilleval.runner import CaseResult, UsageError, collect, run
from skilleval.testfile import Setup

RESULTS = ".skilleval/results/evals/a.eval.yml/t"  # where the results of the test t of FILE are kept
SETTINGS = ".skilleval/config.yml"  # the settings every test of FILE runs with
EXPECT = "expect: [{response: [{contains: qubit}]}]"
QUBIT = EXPECT + "\n"
FIRST = f"first: {{kind: evaluation, task: Write the tests., {EXPECT}}}\n"  # a task before the test's own
USES_FIRST = "uses: ./a.eval.yml#first\ntask: Implement slugify.\n"
CHAIN = USES_FIRST + QUBIT
REPORTED = USES_FIRST + """\
expect:
  - response:
      - urls: {count: {max: 9}}
  - file: {with_path: gone.md, severity: warn}
"""


def reply(
    text: str = "It holds a qubit.", tokens: int = 10, cost_usd: float = 0.01, denied: str | None = None, transcript: str = "{}\n"
) -> Reply:
    return Reply(text, "conversation-1", tokens, cost_usd, transcript, denied)


@dataclass
class Harness:
    """Stands in for `harness.ask`: writes `files` into the workspace and answers with the next
    of `replies`, raising the one that is an exception. `asked` keeps each task with the reply
    before it and the workspace as it was found, `folders` the workspace, `configs` the
    settings, `given` the rest of what it was called with."""

    replies: Sequence[Reply | BaseException] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    asked: list[tuple[str, Reply | None, dict[str, str]]] = field(default_factory=list)
    folders: list[Path] = field(default_factory=list)
    configs: list[Config] = field(default_factory=list)
    given: list[tuple[Setup, str, int | None, float | None]] = field(default_factory=list)

    def __call__(
        self, task: str, setup: Setup, model: str, folder: Path, previous: Reply | None = None,
        *, config: Config, max_tokens: int | None = None, max_budget_usd: float | None = None,
    ) -> Reply:
        self.asked.append((task, previous, tree(folder)))
        self.folders.append(folder)
        self.configs.append(config)
        self.given.append((setup, model, max_tokens, max_budget_usd))
        for path, text in self.files.items():
            (folder / path).parent.mkdir(parents=True, exist_ok=True)
            (folder / path).write_text(text, encoding="utf-8")
        answer = self.replies[len(self.asked) - 1]
        if isinstance(answer, BaseException):
            raise answer
        return answer


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    fake = Harness()
    monkeypatch.setattr("skilleval.evaluation.harness.ask", fake)
    return fake


def write(project: Project, test: str, templates: str = "", setup: str = "{harness: user_local}") -> None:
    """Write the test file: the evaluation `t` holding the lines of `test`, and the `templates:` entries."""
    head = f"kind: evaluation\nmodel: claude-sonnet-5\nsetup: {setup}\n"
    section = "templates:\n" + textwrap.indent(templates, "  ") if templates else ""
    project.write(FILE, "root: pyproject.toml\n" + section + "tests:\n  t:\n" + textwrap.indent(head + test, "    "))


def run_one(project: Project, test: str, templates: str = "", setup: str = "{harness: user_local}") -> CaseResult:
    write(project, test, templates, setup)
    (result,) = run(collect([FILE]))
    return result


def reported(result: CaseResult) -> list[tuple[str, str, str]]:
    """What each result is about, its check and its status; one that did not pass says why."""
    assert all(c.findings for c in result.checks if c.status != "passed")
    return [(c.prefix, c.check.name, c.status) for c in result.checks]


def test_an_evaluation_is_one_nameless_case_that_takes_no_brackets(project: Project) -> None:
    write(project, "task: Say hi.\n")
    assert [case.node_id for case in collect([FILE])] == [f"{FILE}::t"]
    with pytest.raises(UsageError):
        collect([f"{FILE}::t[Say hi.]"])


@pytest.mark.parametrize("name", ["user_local", "blank"])
def test_the_harness_is_given_the_task_as_written_its_setup_and_a_workspace_holding_the_working_folder_alone(
    project: Project, harness: Harness, name: str
) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    harness.replies = [reply()]
    result = run_one(project, "task: ' Review the patch in pr.diff. '\nmax_tokens: 100\nmax_budget_usd: 0.5\n" + QUBIT,
                     setup=f"{{harness: {name}, permissions: bypass, working_folder: fixtures/pr}}")
    setup = Setup(name, "bypass", working_folder=project.root / "fixtures/pr")
    assert harness.asked == [(" Review the patch in pr.diff. ", None, {"pr.diff": "+ x\n"})]
    assert harness.given == [(setup, "claude-sonnet-5", 100, 0.5)]
    assert (result.status, reported(result)) == ("passed", [("response", "contains", "passed")])


@pytest.mark.parametrize("answer, test, status, expected", [
    (reply("No idea."), "", "passed", []),
    (reply("No idea."), "expect: [{response: [{contains: qubit}], severity: warn}]\n", "passed", [("response", "contains", "warned")]),
    (reply(), "expect: [{file: {with_path: made/notes.md, words: {max: 1}}}]\n", "failed",
     [("made/notes.md", "file", "passed"), ("made/notes.md", "words", "failed")]),
    (reply(denied="Bash(rm -rf /)"), QUBIT, "failed", [("", "permissions", "failed")]),
    (reply(tokens=100, cost_usd=0.5), "max_tokens: 100\nmax_budget_usd: 0.5\n", "passed", []),
    (reply(cost_usd=math.nextafter(0.5, 1)), "max_budget_usd: 0.5\n" + QUBIT, "failed", [("", "max_budget_usd", "failed")]),
    (reply(tokens=101, denied="Bash(ls)"), "max_tokens: 100\n", "failed", [("", "max_tokens", "failed")]),
    (reply(tokens=101, cost_usd=0.51), "max_tokens: 100\nmax_budget_usd: 0.5\n", "failed",
     [("", "max_tokens", "failed"), ("", "max_budget_usd", "failed")]),
], ids=["no expect", "a warning never fails", "a file the task left", "a permission request", "at the limits",
        "above the budget by the least there is", "a limit comes before a permission request", "above both limits"])
def test_one_task_passes_or_fails_on_its_checks_a_permission_request_and_the_limits(
    project: Project, harness: Harness, answer: Reply, test: str, status: str, expected: list[tuple[str, str, str]]
) -> None:
    harness.replies, harness.files = [answer], {"made/notes.md": "two words"}
    result = run_one(project, "task: Explain quantum computing.\n" + test)
    assert (result.status, reported(result)) == (status, expected)
    said = {c.check.name: f.message for c in result.checks for f in c.findings}
    assert "permissions" not in said or answer.denied in said["permissions"]
    assert said.get("max_budget_usd") in (None, f"{answer.cost_usd} used, above the maximum of 0.5")
    assert (project.root / RESULTS / "conversation.jsonl").read_text(encoding="utf-8") == answer.transcript  # a limit's too


@pytest.mark.parametrize("replies, limit, status, expected", [
    ([reply(tokens=60), reply(tokens=90)], "max_tokens: 100\n", "passed",
     [("task 1: response", "contains", "passed"), ("task 2: response", "contains", "passed")]),
    ([reply("No idea."), reply()], "", "failed", [("task 1: response", "contains", "failed"), ("task 2: response", "contains", "passed")]),
    ([reply(denied="Edit(utils.py)"), reply()], "", "failed", [("task 1", "permissions", "failed"), ("task 2: response", "contains", "passed")]),
    ([reply(tokens=60), reply(tokens=120)], "max_tokens: 100\n", "failed", [("task 1: response", "contains", "passed"), ("task 2", "max_tokens", "failed")]),
    ([reply(tokens=101)], "max_tokens: 100\n", "failed", [("", "max_tokens", "failed")]),
    ([HarnessError("the harness does not know the model claude-sonnet-5")], "", "error", []),
    ([reply("No idea."), HarnessError("the harness crashed")], "", "error", []),
], ids=["both pass, the tokens of a reply counting the whole conversation", "a failing check leaves the next task to run", "so does a permission request",
        "the limits cover the whole chain", "a limit reached ends the chain", "so does an error",
        "an error leaves nothing but its reason"])
def test_chained_tasks_run_in_order_in_one_workspace_and_one_conversation(
    project: Project, harness: Harness, replies: list[Reply | HarnessError], limit: str, status: str,
    expected: list[tuple[str, str, str]],
) -> None:
    project.write("fixtures/utils/strings.py", "def slugify(): ...\n")
    harness.replies, harness.files = replies, {"made.txt": "by a task"}
    result = run_one(project, limit + CHAIN, FIRST, setup="{harness: user_local, working_folder: fixtures/utils}")
    seed = {"strings.py": "def slugify(): ...\n"}
    second = [("Implement slugify.", replies[0], seed | harness.files)]
    assert harness.asked == [("Write the tests.", None, seed), *second[:len(replies) - 1]]
    assert {tokens for _, _, tokens, _ in harness.given} == {100 if limit else None}
    assert (result.status, reported(result)) == (status, expected)
    assert result.reason == (str(replies[-1]) if status == "error" else None)


@pytest.mark.parametrize("written, config", [
    (None, {}),
    ("backend: claude_api\nANTHROPIC_API_KEY: sk-ant-api03-key\n", {"backend": "claude_api", "anthropic_api_key": "sk-ant-api03-key"}),
], ids=["the default, written", "as written"])
def test_every_task_is_given_the_settings_read_as_the_test_starts_from_a_folder_git_ignores(
    project: Project, harness: Harness, written: str | None, config: dict[str, str]
) -> None:
    if written is not None:
        project.write(SETTINGS, written)
    harness.replies = [reply(), reply()]
    run_one(project, CHAIN, FIRST)
    assert harness.configs == [Config(project.root / SETTINGS, **config)] * 2
    assert (project.root / SETTINGS).is_file()
    assert "*" in (project.root / ".skilleval/.gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("written", ["backend: claude_web\n", None], ids=["a bad file", "a folder in its place"])
def test_settings_that_cannot_be_read_are_an_error_naming_the_file_that_asks_nothing_and_keep_the_workspace_as_filled(
    project: Project, harness: Harness, written: str | None
) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    project.write(f"{RESULTS}/conversation.jsonl", "of the run before\n")
    stale = locate(project.root / FILE, "t")
    stale.mkdir(parents=True)
    (stale / "killed.txt").write_text("left by a run that was killed", encoding="utf-8")
    if written is None:
        (project.root / SETTINGS).mkdir()
    else:
        project.write(SETTINGS, written)
    result = run_one(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
    assert (result.status, harness.asked) == ("error", [])
    assert str(project.root / SETTINGS) in (result.reason or "")
    assert tree(project.root / RESULTS) == {"workspace/pr.diff": "+ x\n", "conversation.jsonl": ""}  # nothing of a run before


def test_settings_that_cannot_be_written_are_an_error_naming_the_file_that_asks_nothing(project: Project, harness: Harness) -> None:
    project.write(".skilleval", "a file where the folder of the settings goes")
    result = run_one(project, "task: Review the patch.\n")
    assert (result.status, harness.asked) == ("error", [])
    assert str(project.root / SETTINGS) in (result.reason or "")


def test_a_chain_of_three_resumes_each_task_from_the_reply_to_the_one_before(project: Project, harness: Harness) -> None:
    harness.replies = [reply("one qubit"), reply("two qubits"), reply("three qubits")]
    second = "second: {kind: evaluation, task: Implement slugify.}\n"
    run_one(project, "uses: [./a.eval.yml#first, ./a.eval.yml#second]\ntask: Document it.\n", FIRST + second)
    assert [(task, previous) for task, previous, _ in harness.asked] == [
        ("Write the tests.", None), ("Implement slugify.", harness.replies[0]), ("Document it.", harness.replies[1]),
    ]


def test_ctrl_c_mid_chain_keeps_the_results_and_goes_on(project: Project, harness: Harness) -> None:
    harness.replies = [reply(transcript="1\n"), KeyboardInterrupt()]
    write(project, CHAIN, FIRST)
    cases = collect([FILE])
    with pytest.raises(KeyboardInterrupt):
        run(cases)
    assert (project.root / RESULTS / "conversation.jsonl").read_text(encoding="utf-8") == "1\n"


def test_a_workspace_the_harness_removed_leaves_results_holding_the_conversation_alone(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def ask(task: str, setup: Setup, model: str, folder: Path, *args: Any, **kwargs: Any) -> Reply:
        shutil.rmtree(folder)
        return reply(transcript="1\n")

    monkeypatch.setattr("skilleval.evaluation.harness.ask", ask)
    assert run_one(project, "task: Review the patch.\n").status == "passed"
    assert tree(project.root / RESULTS) == {"conversation.jsonl": "1\n"}


def test_a_move_that_fails_partway_leaves_what_it_kept_ignored_by_git_and_is_an_error(
    project: Project, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.replies, harness.files = [reply(transcript="1\n")], {"a.txt": "moved", "b.txt": "not moved"}

    def move(source: Path, target: Path) -> None:
        target.mkdir()
        shutil.copy(source / "a.txt", target)
        raise OSError("cannot read b.txt")

    monkeypatch.setattr(shutil, "move", move)
    result = run_one(project, "task: Review the patch.\n")
    assert result.status == "error"
    assert result.reason == f"cannot keep the results in {project.root / RESULTS}: cannot read b.txt"
    assert tree(project.root / RESULTS) == {"conversation.jsonl": "1\n", "workspace/a.txt": "moved"}
    assert "*" in (project.root / ".skilleval/.gitignore").read_text(encoding="utf-8").splitlines()


def test_a_workspace_that_cannot_be_filled_is_an_error_and_asks_nothing(project: Project, harness: Harness) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    write(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
    cases = collect([FILE])
    shutil.rmtree(project.root / "fixtures/pr")
    project.write("fixtures/pr", "a file where the folder was")
    project.write(f"{RESULTS}/conversation.jsonl", "of the run before\n")
    (result,) = run(cases)
    assert (result.status, harness.asked) == ("error", [])
    assert result.reason
    assert tree(project.root / RESULTS) == {"conversation.jsonl": ""}  # nothing of the run before is left to mislead


@pytest.mark.parametrize("second", [reply(transcript='{"task": 2}\n'), HarnessError("the harness crashed")],
                         ids=["every task returned", "the harness failed on the second"])
def test_the_results_hold_the_workspace_as_the_test_left_it_and_the_conversation_of_every_task_that_returned(
    project: Project, harness: Harness, second: Reply | HarnessError
) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    harness.replies, harness.files = [reply(transcript='{"task": 1}\n{"é": 1}\n'), second], {"pr.diff": "rewritten"}
    run_one(project, CHAIN, FIRST, setup="{harness: user_local, working_folder: fixtures/pr}")
    results = project.root / RESULTS
    assert harness.folders == [locate(project.root / FILE, "t")] * 2  # where the model works, out of the project
    assert not harness.folders[0].exists()
    assert tree(results) == {
        "workspace/pr.diff": "rewritten",
        "conversation.jsonl": '{"task": 1}\n{"é": 1}\n' + (second.transcript if isinstance(second, Reply) else ""),
    }
    assert tree(project.root / "fixtures/pr") == {"pr.diff": "+ x\n"}


def test_the_results_of_a_file_without_root_are_kept_beside_it(project: Project, harness: Harness) -> None:
    project.write("evals/fixtures/pr/pr.diff", "+ x\n")
    harness.replies, harness.files = [reply(transcript="1\n")], {"pr.diff": "rewritten"}
    project.write(FILE, "tests:\n  t: {kind: evaluation, model: claude-sonnet-5, task: Review the patch.,\n"
                        "      setup: {harness: user_local, working_folder: ./fixtures/pr}}\n")
    (result,) = run(collect([FILE]))
    assert result.status == "passed"
    assert tree(project.root / "evals/.skilleval/results/a.eval.yml/t") == {"workspace/pr.diff": "rewritten", "conversation.jsonl": "1\n"}
    assert "*" in (project.root / "evals/.skilleval/.gitignore").read_text(encoding="utf-8").splitlines()
    assert not (project.root / ".skilleval").exists()


@pytest.mark.parametrize("replies, reason", [
    ([reply()], "cannot keep the results in {results}: "),
    ([HarnessError("the harness crashed")], "the harness crashed"),
], ids=["an error of its own", "the chain's error wins"])
def test_results_that_cannot_be_kept_are_an_error(
    project: Project, harness: Harness, replies: list[Reply | HarnessError], reason: str
) -> None:
    project.write(".skilleval/results", "a file where skilleval keeps its results")
    harness.replies = replies
    result = run_one(project, "task: Review the patch.\n")
    assert result.status == "error"
    assert result.reason is not None
    assert result.reason.startswith(reason.format(results=project.root / RESULTS))


def test_a_run_replaces_the_results_folder_of_its_test_whole_and_nothing_else(project: Project, harness: Harness) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    harness.replies, harness.files = [reply(transcript="1\n"), reply(transcript="2\n")], {"first.txt": "by the task"}
    run_one(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
    project.write(f"{RESULTS}/notes.md", "left in the results")
    kept = {".skilleval/results/evals/a.eval.yml/u/conversation.jsonl": "another test's\n", "evals/notes.md": "mine"}
    for path, text in kept.items():
        project.write(path, text)
    (project.root / ".skilleval/.gitignore").unlink(missing_ok=True)
    harness.files = {"second.txt": "by the task"}
    run_one(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
    assert [found for _, _, found in harness.asked] == [{"pr.diff": "+ x\n"}] * 2  # every run starts from the working folder
    assert tree(project.root / RESULTS) == {"workspace/pr.diff": "+ x\n", "workspace/second.txt": "by the task", "conversation.jsonl": "2\n"}
    assert all((project.root / path).read_text(encoding="utf-8") == text for path, text in kept.items())
    assert "*" in (project.root / ".skilleval/.gitignore").read_text(encoding="utf-8").splitlines()


def test_an_evaluation_whose_needed_test_failed_is_skipped_and_asks_nothing(project: Project, harness: Harness) -> None:
    project.tests("gate: {kind: static-check, prompt: hi, constraints: [{contains: Usage}]}\n"
                  "t: {kind: evaluation, needs: gate, model: claude-sonnet-5, setup: {harness: user_local}, task: Say hi.}\n")
    results = run(collect([FILE]))
    assert [result.status for result in results] == ["failed", "skipped"]
    assert harness.asked == []
    assert "workspace" not in project.cli(FILE, "-v")[1]
    assert not (project.root / ".skilleval").exists()


def test_report_prefixes_the_findings_and_names_the_workspace_under_a_failure_and_with_v_not_when_all_passed(
    project: Project, harness: Harness
) -> None:
    seen = reply("It holds a qubit, see https://x.io")
    harness.replies = [reply("No idea."), seen] + [seen] * 4  # three runs of two tasks
    write(project, REPORTED, FIRST)
    workspace = f"  workspace: {project.root / RESULTS / 'workspace'}"
    code, failed = project.cli(FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{FILE}::t FAILED\n  task 1: response: contains: " in failed
    assert workspace in failed
    assert f"  task 2: response: urls: detected https://x.io\n{workspace}" in project.cli(FILE, "-v")[1]
    code, passed = project.cli(FILE)
    assert code == ExitCode.OK
    assert "workspace" not in passed


def test_an_error_says_how_many_checks_of_every_task_went_with_it_and_names_the_workspace(
    project: Project, harness: Harness
) -> None:
    harness.replies = [reply(), HarnessError("the harness crashed")]
    write(project, REPORTED, FIRST)
    out = project.cli(FILE)[1]
    assert f"  the harness crashed; 3 checks skipped\n  workspace: {project.root / RESULTS / 'workspace'}" in out


def test_a_directory_collects_nothing_of_the_results_kept(project: Project, harness: Harness) -> None:
    other = "fixtures/pr/other.eval.yml"  # a test file in the working folder, copied into the workspace
    project.write(other, "tests:\n  x: {kind: static-check, prompt: hello, lint: [chars]}\n")
    harness.replies = [reply()]
    run_one(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
    assert (project.root / RESULTS / "workspace/other.eval.yml").is_file()
    assert [case.node_id for case in collect([])] == [f"{FILE}::t", f"{other}::x"]
