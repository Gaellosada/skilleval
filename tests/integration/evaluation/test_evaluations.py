"""An evaluation through `collect`, `run` and `main`, with `Harness` in place of the harness: the
chain of tasks, what fails or stops it, the workspace and the report. Specified in
specs/evaluations.md."""

import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from conftest import Project, todo, tree

from skilleval import ExitCode
from skilleval.evaluation.harness import HarnessError, Reply
from skilleval.evaluation.workspace import locate
from skilleval.runner import CaseResult, UsageError, collect, run
from skilleval.testfile import Setup

pytestmark = todo

FILE = "evals/a.eval.yml"
QUBIT = "expect: [{response: [{contains: qubit}]}]\n"
FIRST = "first: {kind: evaluation, task: Write the tests., " + QUBIT[:-1] + "}\n"  # a task before the test's own
CHAIN = "uses: ./a.eval.yml#first\ntask: Implement slugify.\n" + QUBIT


def reply(text: str = "It holds a qubit.", tokens: int = 10, cost_usd: float = 0.01, denied: str | None = None) -> Reply:
    return Reply(text, "conversation-1", tokens, cost_usd, denied)


@dataclass
class Harness:
    """Stands in for `harness.ask`: writes `files` into the workspace and answers with the next
    of `replies`, raising the one that is an error. `asked` keeps each task with the reply
    before it and the workspace as it was found."""

    replies: list[Reply | HarnessError] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    asked: list[tuple[str, Reply | None, dict[str, str]]] = field(default_factory=list)

    def __call__(
        self, task: str, setup: Setup, model: str, folder: Path, previous: Reply | None = None,
        *, max_tokens: int | None = None, max_budget_usd: float | None = None,
    ) -> Reply:
        self.asked.append((task, previous, tree(folder)))
        for path, text in self.files.items():
            (folder / path).parent.mkdir(parents=True, exist_ok=True)
            (folder / path).write_text(text, encoding="utf-8")
        answer = self.replies[len(self.asked) - 1]
        if isinstance(answer, HarnessError):
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
    project.write(FILE, "root: pyproject.toml\ntemplates:\n" + textwrap.indent(templates, "  ") + "  unused: {kind: static-check}\n"
                  "tests:\n  t:\n" + textwrap.indent(head + test, "    "))


def run_one(project: Project, test: str, templates: str = "", setup: str = "{harness: user_local}") -> CaseResult:
    write(project, test, templates, setup)
    (result,) = run(collect([FILE]))
    return result


def reported(result: CaseResult) -> list[tuple[str, str, str]]:
    return [(c.prefix, c.check.name, c.status) for c in result.checks]


def test_an_evaluation_is_one_nameless_case_that_takes_no_brackets(project: Project) -> None:
    write(project, "task: Say hi.\n")
    assert [case.node_id for case in collect([FILE])] == [f"{FILE}::t"]
    with pytest.raises(UsageError):
        collect([f"{FILE}::t[Say hi.]"])


def test_the_model_is_given_the_task_as_written_in_a_workspace_holding_the_working_folder_alone(
    project: Project, harness: Harness
) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    harness.replies = [reply()]
    result = run_one(project, "task: Review the patch in pr.diff.\n" + QUBIT, setup="{harness: user_local, working_folder: fixtures/pr}")
    assert harness.asked == [("Review the patch in pr.diff.", None, {"pr.diff": "+ x\n"})]
    assert result.status == "passed"


@pytest.mark.parametrize("answer, test, status, expected", [
    (reply("No idea."), "", "passed", []),
    (reply(), QUBIT, "passed", [("response", "contains", "passed")]),
    (reply("No idea."), QUBIT, "failed", [("response", "contains", "failed")]),
    (reply("No idea."), "expect: [{response: [{contains: qubit}], severity: warn}]\n", "passed", [("response", "contains", "warned")]),
    (reply(), "expect: [{file: {with_path: made/notes.md, words: {max: 1}}}]\n", "failed",
     [("made/notes.md", "file", "passed"), ("made/notes.md", "words", "failed")]),
    (reply(), "expect: [{file: {with_path: missing.md, severity: warn}}]\n", "passed", [("missing.md", "file", "warned")]),
    (reply(denied="Bash(rm -rf /)"), QUBIT, "failed", [("", "permissions", "failed")]),
    (reply(tokens=100, cost_usd=0.5), "max_tokens: 100\nmax_budget_usd: 0.5\n", "passed", []),
    (reply(tokens=101), "max_tokens: 100\n" + QUBIT, "failed", [("", "max_tokens", "failed")]),
    (reply(cost_usd=0.51), "max_budget_usd: 0.5\n" + QUBIT, "failed", [("", "max_budget_usd", "failed")]),
], ids=["no expect", "a check that passes", "a check that fails", "a warning never fails", "a file the task left",
        "a missing file, as a warning", "a permission request", "at the limits", "above the tokens", "above the budget"])
def test_one_task_passes_or_fails_on_its_checks_a_permission_request_and_the_limits(
    project: Project, harness: Harness, answer: Reply, test: str, status: str, expected: list[tuple[str, str, str]]
) -> None:
    harness.replies, harness.files = [answer], {"made/notes.md": "two words"}
    result = run_one(project, "task: Explain quantum computing.\n" + test)
    assert (result.status, reported(result)) == (status, expected)
    assert all(answer.denied in f.message for c in result.checks if c.check.name == "permissions" for f in c.findings)


@pytest.mark.parametrize("replies, limit, status, expected", [
    ([reply(), reply()], "", "passed", [("task 1: response", "contains", "passed"), ("task 2: response", "contains", "passed")]),
    ([reply("No idea."), reply()], "", "failed", [("task 1: response", "contains", "failed"), ("task 2: response", "contains", "passed")]),
    ([reply(denied="Edit(utils.py)"), reply()], "", "failed", [("task 1", "permissions", "failed"), ("task 2: response", "contains", "passed")]),
    ([reply(tokens=60), reply(tokens=120)], "max_tokens: 100\n", "failed", [("task 1: response", "contains", "passed"), ("task 2", "max_tokens", "failed")]),
    ([reply(tokens=101)], "max_tokens: 100\n", "failed", [("task 1", "max_tokens", "failed")]),
    ([HarnessError("the harness does not know the model claude-sonnet-5")], "", "error", []),
], ids=["both pass", "a failing check leaves the next task to run", "so does a permission request",
        "the limits cover the whole chain", "a limit reached ends the chain", "so does an error"])
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
    assert (result.status, reported(result)) == (status, expected)
    assert result.reason == (str(replies[0]) if status == "error" else None)


def test_the_workspace_is_left_as_the_test_ended_and_filled_again_by_the_next_run(project: Project, harness: Harness) -> None:
    project.write("fixtures/pr/pr.diff", "+ x\n")
    harness.replies, harness.files = [reply(), reply()], {"pr.diff": "rewritten", "made.txt": "by the task"}
    for _ in range(2):
        run_one(project, "task: Review the patch.\n", setup="{harness: user_local, working_folder: fixtures/pr}")
        assert tree(locate(project.root / FILE, "t")) == harness.files
    assert [found for _, _, found in harness.asked] == [tree(project.root / "fixtures/pr")] * 2 == [{"pr.diff": "+ x\n"}] * 2


def test_an_evaluation_whose_needed_test_failed_is_skipped_and_asks_nothing(project: Project, harness: Harness) -> None:
    project.tests("gate: {kind: static-check, prompt: hi, constraints: [{contains: Usage}]}\n"
                  "t: {kind: evaluation, needs: gate, model: claude-sonnet-5, setup: {harness: user_local}, task: Say hi.}\n")
    assert [result.status for result in run(collect([FILE]))] == ["failed", "skipped"]
    assert harness.asked == []


def test_report_prefixes_the_findings_and_names_the_workspace_under_a_failure_and_with_v(
    project: Project, harness: Harness
) -> None:
    harness.replies = [reply("No idea."), reply(), reply(), reply()]
    write(project, CHAIN, FIRST)
    workspace = f"  workspace: {locate(project.root / FILE, 't')}"
    code, failed = project.cli(FILE)
    assert code == ExitCode.TESTS_FAILED
    assert f"{FILE}::t FAILED\n  task 1: response: contains: " in failed
    assert workspace in failed
    assert workspace in project.cli(FILE, "-v")[1]
    assert "workspace" not in project.cli(FILE)[1]
