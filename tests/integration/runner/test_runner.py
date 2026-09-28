"""`skilleval.runner`: discovery, node ids, selection and `run`, per specs/cli.md and specs/README.md."""

import textwrap
from pathlib import Path

import pytest
from conftest import Project

from skilleval import runner
from skilleval.runner import CaseResult, UsageError, collect, run
from skilleval.static import CHECKS
from skilleval.testfile import LoadError

FILE = "evals/a.eval.yml"
CHARS = "t:\n  kind: static-check\n  prompt: {file: docs/x.md}\n  lint: [chars]\n"
# a test for each prompt form: a single file, a glob matching two files, a text
FORMS = """
t: {kind: static-check, prompt: {file: docs/x.md}, lint: [chars]}
g: {kind: static-check, prompt: {include: docs/g/*.md}, lint: [chars]}
n: {kind: static-check, prompt: hello, lint: [chars]}
"""


def ids(cases: list[runner.Case]) -> list[str]:
    return [case.node_id for case in cases]


def forms(project: Project) -> None:
    for path in ("docs/x.md", "docs/g/a.md", "docs/g/b.md"):
        project.write(path, "hello")
    project.tests(FORMS)


def statuses(project: Project, tests: str) -> dict[str, CaseResult]:
    """Run every case of the written file and key the results by test id: a glob's cases share one key, the last kept."""
    project.tests(tests)
    return {r.case.test.id: r for r in run(collect([FILE]))}


# --- discovery -----------------------------------------------------------------


def test_discovery_finds_eval_files_below_the_directory_sorted_skipping_dot_vendored_and_other_yaml(project: Project) -> None:
    project.write("docs/x.md", "hello")
    found = ["evals/a.eval.yml", "evals/b.eval.yaml", "evals/c.eval.yml", "evals/sub/d.eval.yml"]
    skipped = [".hidden/e.eval.yml", "evals/node_modules/e.eval.yml", "venv/e.eval.yml", "site-packages/e.eval.yml"]
    for path in found[::-1] + skipped:
        project.tests(CHARS, path)
    for path in ("evals/ci.yml", "evals/other.yaml", "evals/workflows/eval.yml"):
        project.write(path, "on: push\n")
    assert ids(collect([])) == [f"{path}::t[docs/x.md]" for path in found]


@pytest.mark.parametrize("head, include", [("root: pyproject.toml\n", "'**/SKILL.md'"), ("", "./**/SKILL.md")],
                         ids=["from the root", "from the directory of a file without root"])
def test_an_include_never_enters_a_skilleval_folder(project: Project, head: str, include: str) -> None:
    skill = "evals/skills/r/SKILL.md"
    copies = [".skilleval/results/evals/a.eval.yml/t/workspace/.claude/skills/r/SKILL.md",  # a skill in a workspace kept
              "evals/.skilleval/results/a.eval.yml/t/workspace/.claude/skills/r/SKILL.md", "evals/skills/.skilleval/SKILL.md"]
    for path in (skill, *copies):
        project.write(path, "hello")
    project.write(FILE, head + f"tests:\n  s: {{kind: static-check, prompt: {{include: {include}}}, lint: [chars]}}\n")
    assert ids(collect([FILE])) == [f"{FILE}::s[{skill}]"]


@pytest.mark.parametrize("args, files", [
    (["checks.yaml"], ["checks.yaml"]),
    ([f"./{FILE}"], [FILE]),
    (["evals/"], [FILE, "evals/b.eval.yml"]),
    (["{root}/evals"], [FILE, "evals/b.eval.yml"]),
    (["evals/b.eval.yml", FILE], ["evals/b.eval.yml", FILE]),
    (["evals", FILE], [FILE, "evals/b.eval.yml"]),
], ids=["a file named whatever its name", "dot-slash", "trailing slash", "absolute", "argument order", "a case named twice"])
def test_arguments_collect_files_in_their_order_under_cwd_relative_node_ids_each_case_once(
    project: Project, args: list[str], files: list[str]
) -> None:
    project.write("docs/x.md", "hello")
    for path in (FILE, "evals/b.eval.yml", "checks.yaml"):
        project.tests(CHARS, path)
    assert ids(collect([arg.format(root=project.root) for arg in args])) == [f"{path}::t[docs/x.md]" for path in files]


def test_a_file_named_more_than_once_is_loaded_once(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    forms(project)
    loads: list[Path] = []
    load = runner.load
    monkeypatch.setattr(runner, "load", lambda path: (loads.append(path), load(path))[1])
    collect([f"{FILE}::t", f"{FILE}::n", "evals"])
    assert len(loads) == 1


def test_a_bad_file_raises_load_error(project: Project) -> None:
    project.write(FILE, "test:\n  t:\n    kind: static-check\n")
    with pytest.raises(LoadError):
        collect([FILE])


# --- node ids ------------------------------------------------------------------


@pytest.mark.parametrize("files, prompt, keys", [
    ([], "hello", None),
    (["docs/x.md"], "{file: docs/x.md}", ["docs/x.md"]),
    ([], "{file: docs/x.md}", ["docs/x.md"]),
    (["evals/x.md"], "{file: ./x.md}", ["evals/x.md"]),
    (["docs/b.md", "docs/c.md", "docs/a.md"], "{include: docs/*.md}", ["docs/a.md", "docs/b.md", "docs/c.md"]),
    (["docs/a.md", "docs/fixtures/b.md"], '{include: "docs/**/*.md", exclude: "**/fixtures/**"}', ["docs/a.md"]),
    (["docs/b.md", "docs/fixtures/b.md"], '{include: "docs/**/*.md", exclude: "docs/fixtures/**"}', ["docs/b.md"]),
    ([".claude/skills/x/SKILL.md"], '{include: "**/SKILL.md"}', [".claude/skills/x/SKILL.md"]),
    ([], "{include: docs/*.md}", None),
], ids=["text: bare", "single file", "single file missing", "dot-slash, written from the cwd", "glob: one per match, sorted",
        "exclude", "exclude from where the glob started", "** crosses dot directories", "glob matching nothing: bare"])
def test_node_id_is_file_and_test_with_each_prompt_path_in_brackets(
    project: Project, files: list[str], prompt: str, keys: list[str] | None
) -> None:
    for path in files:
        project.write(path, "hello")
    project.tests(f"t: {{kind: static-check, prompt: {prompt}, lint: [chars]}}\n")
    assert ids(collect([FILE])) == ([f"{FILE}::t[{key}]" for key in keys] if keys else [f"{FILE}::t"])


def test_a_case_carries_its_file_its_test_and_the_path_of_its_prompt(project: Project) -> None:
    forms(project)
    cases = collect([FILE])
    assert [(c.test.id, c.prompt_path and c.prompt_path.resolve()) for c in cases] == [
        ("t", (project.root / "docs/x.md").resolve()),
        ("g", (project.root / "docs/g/a.md").resolve()),
        ("g", (project.root / "docs/g/b.md").resolve()),
        ("n", None),
    ]
    assert {c.file.path.resolve() for c in cases} == {(project.root / FILE).resolve()}


# --- selection -----------------------------------------------------------------


@pytest.mark.parametrize("node, selected", [
    ("g", ["g[docs/g/a.md]", "g[docs/g/b.md]"]),
    ("g[docs/g/b.md]", ["g[docs/g/b.md]"]),
    ("t", ["t[docs/x.md]"]),
    ("t[docs/x.md]", ["t[docs/x.md]"]),
], ids=["bare: every fanned case", "bracketed: one", "single file, bare", "single file, bracketed"])
def test_a_node_id_selects_the_cases_it_names(project: Project, node: str, selected: list[str]) -> None:
    forms(project)
    assert ids(collect([f"{FILE}::{node}"])) == [f"{FILE}::{s}" for s in selected]


@pytest.mark.parametrize("arg, said", [
    ("evals/missing.eval.yml", "no such file"),
    ("evals::t", "names a file, not a directory"),
    (f"{FILE}::t[docs/x.md]x", "a node id is"),
    (f"{FILE}::[docs/x.md]", "a node id is"),
    (f"{FILE}::nope", "no test 'nope'"),
    (f"{FILE}::g[docs/nope.md]", "is named 'docs/nope.md'"),
    (f"{FILE}::n[docs/x.md]", "takes no brackets"),  # not "no case is named", which invites a search for a key that cannot exist
], ids=["missing path", "a test of a directory", "text after the brackets", "brackets alone", "unknown test",
        "bracket key matching nothing", "brackets on a nameless case"])
def test_a_bad_argument_is_a_usage_error_saying_what_is_wrong(project: Project, arg: str, said: str) -> None:
    forms(project)
    with pytest.raises(UsageError, match=said):
        collect([arg])


@pytest.mark.parametrize("keyword, selected", [
    ("alph", ["alpha"]),
    ("evals", ["alpha", "beta", "gamma"]),
    ("delta", []),
    ("alpha or beta", []),
    ("a or b", ["gamma"]),
], ids=["part of an id", "part of the path", "nothing", "not a boolean expression", "a plain substring"])
def test_keyword_keeps_the_node_ids_containing_it(project: Project, keyword: str, selected: list[str]) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/a or b.md", "hello")
    project.tests("""
        alpha: {kind: static-check, prompt: {file: docs/x.md}, lint: [chars]}
        beta: {kind: static-check, prompt: {file: docs/x.md}, lint: [chars]}
        gamma: {kind: static-check, prompt: {file: docs/a or b.md}, lint: [chars]}
    """)
    assert [c.test.id for c in collect([FILE], keyword=keyword)] == selected


# a static check, an evaluation needing it, and tests needing that evaluation in turn
KINDS = """
s: {kind: static-check, prompt: hello, lint: [chars]}
e: {kind: evaluation, needs: s, model: claude-sonnet-5, setup: {harness: user_local}, task: Say hi.}
f: {kind: evaluation, needs: e, model: claude-sonnet-5, setup: {harness: user_local}, task: Say hi.}
t: {kind: static-check, needs: e, prompt: hello, lint: [chars]}
u: {kind: static-check, needs: t, prompt: hello, lint: [chars]}
"""


@pytest.mark.parametrize("kind, selected", [
    (None, ["s", "e", "f", "t", "u"]),
    ("static-check", ["s", "t", "u"]),
    ("evaluation", ["e", "f"]),
], ids=["no kind", "static checks", "evaluations"])
def test_kind_keeps_the_cases_of_that_kind(project: Project, kind: str | None, selected: list[str]) -> None:
    project.tests(KINDS)
    assert [c.test.id for c in collect([FILE], kind=kind)] == selected


@pytest.mark.parametrize("kind, results", [
    ("static-check", {"s": ("passed", None), "t": ("skipped", "needs e, not selected"), "u": ("skipped", "needs t")}),
    ("evaluation", {"e": ("skipped", "needs s, not selected"), "f": ("skipped", "needs e")}),
], ids=["static checks", "evaluations"])
def test_a_test_needing_one_of_the_other_kind_is_skipped_as_not_selected_and_so_is_what_needs_it(
    project: Project, kind: str, results: dict[str, tuple[str, str | None]]
) -> None:
    project.tests(KINDS)
    assert {r.case.test.id: (r.status, r.reason) for r in run(collect([FILE], kind=kind))} == results


# --- run: statuses -------------------------------------------------------------


@pytest.mark.parametrize("prompt, checks, status, reported", [
    ("{file: docs/x.md}", "lint: [chars]", "passed", ["passed"]),
    ("{file: docs/x.md}", "lint: [chars], constraints: [{contains: Usage}, {words: {max: 5}}]", "failed", ["passed", "failed", "passed"]),
    ("{file: docs/x.md}", "constraints: [{contains: {words: Usage, severity: warn}}]", "passed", ["warned"]),
    ("hello", "lint: [markdown_links, paths_exist]", "passed", ["skipped", "skipped"]),
], ids=["every check passing", "one failing", "only warnings", "a text prompt with only file lints"])
def test_a_case_status_follows_its_checks(
    project: Project, prompt: str, checks: str, status: str, reported: list[str]
) -> None:
    project.write("docs/x.md", "hello")
    result = statuses(project, f"t: {{kind: static-check, prompt: {prompt}, {checks}}}\n")["t"]
    assert (result.status, [c.status for c in result.checks]) == (status, reported)


@pytest.mark.parametrize("prompt, text, said", [
    ("{file: docs/x.md}", None, "docs/x.md"),
    ("{file: docs/x.md}", "---\nname: x\nhello\n", "---"),
    ("{file: docs}", None, "docs"),
    ("{include: docs/*.md}", None, "docs/*.md"),
], ids=["missing", "unclosed frontmatter", "a directory", "include matching nothing"])
def test_a_prompt_that_cannot_be_read_is_an_error_saying_why(project: Project, prompt: str, text: str | None, said: str) -> None:
    project.write("docs/y.txt", "hello")  # docs exists, as a directory
    if text is not None:
        project.write("docs/x.md", text)
    result = statuses(project, f"t: {{kind: static-check, prompt: {prompt}, lint: [chars, markdown_links]}}\n")["t"]
    assert (result.status, result.checks) == ("error", ())
    assert said in result.reason


# --- run: needs ----------------------------------------------------------------

NEEDED = """
passes: {kind: static-check, prompt: {file: docs/usage.md}, constraints: [{contains: Usage}]}
fails: {kind: static-check, prompt: {file: docs/x.md}, constraints: [{contains: Usage}]}
errs: {kind: static-check, prompt: {file: docs/missing.md}, lint: [chars]}
warns: {kind: static-check, prompt: {file: docs/x.md}, constraints: [{contains: {words: Usage, severity: warn}}]}
half: {kind: static-check, prompt: {include: docs/half/*.md}, constraints: [{contains: Usage}]}
"""


def dependent(name: str, needs: str) -> str:
    return f"{name}: {{kind: static-check, needs: {needs}, prompt: {{file: docs/x.md}}, lint: [chars]}}\n"


def test_a_dependent_runs_only_when_every_case_of_what_it_needs_passed(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/usage.md", "Usage")
    project.write("docs/half/a.md", "Usage")
    project.write("docs/half/b.md", "hello")
    tests = NEEDED + "".join(dependent(f"after-{need}", need) for need in ("passes", "fails", "errs", "warns", "half"))
    results = statuses(project, tests + dependent("chained", "after-fails") + dependent("listed", "[passes, fails]"))
    assert {name: (r.status, r.reason) for name, r in results.items() if r.case.test.needs} == {
        "after-passes": ("passed", None),
        "after-fails": ("skipped", "needs fails"),
        "after-errs": ("skipped", "needs errs"),
        "after-warns": ("passed", None),
        "after-half": ("skipped", "needs half"),
        "chained": ("skipped", "needs after-fails"),
        "listed": ("skipped", "needs fails"),
    }
    assert all(r.checks == () for r in results.values() if r.status == "skipped")


def test_a_dependent_is_skipped_naming_a_dependency_the_selection_left_out(project: Project) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/usage.md", "Usage")
    project.tests(NEEDED + dependent("after", "passes"))
    (result,) = run(collect([f"{FILE}::after"]))
    assert (result.status, result.reason) == ("skipped", "needs passes, not selected")


def test_needs_touches_no_filesystem_glob_at_run_time(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.write("docs/x.md", "hello")
    project.write("docs/half/a.md", "Usage")
    project.write("docs/half/b.md", "Usage")
    project.tests(NEEDED + dependent("after", "half"))
    cases = collect([f"{FILE}::half", f"{FILE}::after"])
    monkeypatch.setattr(Path, "glob", lambda *_, **__: pytest.fail("a glob ran at run time"))
    assert [r.status for r in run(cases)] == ["passed", "passed", "passed"]


# --- run: exitfirst ------------------------------------------------------------


@pytest.mark.parametrize("prompt, status", [("docs/x.md", "failed"), ("docs/missing.md", "error")])
def test_exitfirst_stops_after_the_first_failure_or_error_keeping_the_results_before_it(
    project: Project, prompt: str, status: str
) -> None:
    project.write("docs/x.md", "hello")
    project.tests(textwrap.dedent(f"""
        t: {{kind: static-check, prompt: {{file: docs/x.md}}, lint: [chars]}}
        u: {{kind: static-check, prompt: {{file: {prompt}}}, constraints: [{{contains: Usage}}]}}
        v: {{kind: static-check, prompt: {{file: docs/x.md}}, lint: [chars]}}
    """))
    assert [r.status for r in run(collect([FILE]), exitfirst=True)] == ["passed", status]


# --- run: started and finished -------------------------------------------------


@pytest.mark.parametrize("exitfirst", [False, True], ids=["every case", "exitfirst"])
def test_run_gives_each_case_as_it_starts_and_its_result_as_it_ends(
    project: Project, monkeypatch: pytest.MonkeyPatch, exitfirst: bool
) -> None:
    project.tests("""
        t: {kind: static-check, prompt: hello, lint: [chars]}
        u: {kind: static-check, needs: v, prompt: hello, lint: [chars]}
        v: {kind: static-check, prompt: "no\\u00a0break", lint: [chars]}
    """)
    events: list[object] = []
    chars = CHECKS["chars"]
    monkeypatch.setitem(CHECKS, "chars", lambda *args: events.append("checked") or chars(*args))
    results = run(collect([FILE]), exitfirst, started=lambda case: events.append(case.test.id), finished=events.append)
    assert [(r.case.test.id, r.status) for r in results] == [("t", "passed"), ("v", "failed"), ("u", "skipped")][:3 - exitfirst]
    assert events == ["t", "checked", results[0], "v", "checked", results[1], *(["u", results[2]] if not exitfirst else [])]
