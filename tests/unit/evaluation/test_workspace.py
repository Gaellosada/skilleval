"""`skilleval.evaluation.workspace`: where a test's workspace is and how it is filled."""

import os
import subprocess
import sys
import tempfile

import pytest
from conftest import Project, tree

from skilleval.evaluation.workspace import fill, home, ignore, locate, results

LOCATE = "import sys, pathlib, skilleval.evaluation.workspace as w; print(w.locate(pathlib.Path(sys.argv[1]), sys.argv[2]))"


def test_the_same_test_gets_the_same_folder_in_another_run_and_every_test_its_own(project: Project) -> None:
    a, b = project.root / "evals/a.eval.yml", project.root / "other/a.eval.yml"
    here = locate(a, "t")
    env = os.environ | {"TMPDIR": tempfile.gettempdir(), "PYTHONHASHSEED": "random"}  # a fresh hash seed, as any run has
    there = subprocess.run([sys.executable, "-c", LOCATE, str(a), "t"], env=env, capture_output=True, text=True, check=True)
    assert there.stdout.strip() == str(here)
    assert len({here, locate(a, "u"), locate(b, "t")}) == 3


def test_workspace_is_in_the_temporary_directory_under_names_that_say_nothing(project: Project) -> None:
    folder = locate(project.root / "evals/refactor.eval.yml", "split-utils")
    shared, own = folder.relative_to(tempfile.gettempdir()).parts
    assert not any(word in (shared + own).lower() for word in ("skilleval", "eval", "test", "refactor", "split"))
    assert not folder.is_relative_to(project.root)
    assert not folder.exists()


@pytest.mark.parametrize("stale", [True, False], ids=["emptied", "created"])
@pytest.mark.parametrize("seed", [{"pkg/utils.py": "x = 1\n", ".claude/settings.json": "{}"}, {}], ids=["filled", "left empty"])
def test_fill_leaves_in_the_workspace_the_contents_of_the_working_folder_and_nothing_else(
    project: Project, stale: bool, seed: dict[str, str]
) -> None:
    folder = locate(project.root / "evals/a.eval.yml", "t")
    working_folder = project.root / "fixtures/utils" if seed else None
    for path, text in seed.items():
        project.write(f"fixtures/utils/{path}", text)
    if stale:
        (folder / "sub").mkdir(parents=True)
        (folder / "sub/stale.txt").write_text("left by the run before", encoding="utf-8")
    fill(folder, working_folder)
    assert tree(folder) == seed
    assert {p.name for p in folder.iterdir()} == {path.split("/")[0] for path in seed}  # no directory left either
    assert working_folder is None or tree(working_folder) == seed


def test_fill_copies_nothing_named_skilleval_at_any_depth(project: Project) -> None:
    ordinary = {"pkg/utils.py": "x = 1\n", "docs/usage.md": "Usage"}
    skillevals = {".skilleval/config.yml": "CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-token\n", "pkg/.skilleval/config.yml": "",
                  ".skilleval/results/evals/a.eval.yml/t/conversation.jsonl": "{}\n", "docs/.skilleval": "a file of that name"}
    for path, text in (ordinary | skillevals).items():
        project.write(f"fixtures/utils/{path}", text)
    folder = locate(project.root / "evals/a.eval.yml", "t")
    fill(folder, project.root / "fixtures/utils")
    assert tree(folder) == ordinary
    assert list(folder.rglob(".skilleval")) == []  # no folder of that name left empty either
    assert tree(project.root / "fixtures/utils") == ordinary | skillevals


def test_fill_copies_a_symbolic_link_as_a_link_without_following_it(project: Project) -> None:
    project.write("fixtures/utils/pkg/real.txt", "x = 1\n")
    links = {"file.txt": "pkg/real.txt", "folder": "pkg", "dangling.txt": "nowhere.txt"}
    for name, target in links.items():
        (project.root / "fixtures/utils" / name).symlink_to(target)
    folder = locate(project.root / "evals/a.eval.yml", "t")
    fill(folder, project.root / "fixtures/utils")
    assert {name: os.readlink(folder / name) for name in links} == links


@pytest.mark.parametrize("where", ["in the project", "beside the workspaces", "the folder of the workspaces", "in a workspace"])
def test_fill_refuses_a_folder_that_is_not_a_workspace_and_leaves_it_as_it_is(project: Project, where: str) -> None:
    workspace = locate(project.root / "evals/a.eval.yml", "t")
    folder = {
        "in the project": project.root / "workspace",
        "beside the workspaces": workspace.parent.parent / "other",
        "the folder of the workspaces": workspace.parent,
        "in a workspace": workspace / "sub",
    }[where]
    folder.mkdir(parents=True)
    (folder / "kept.txt").write_text("not skilleval's to delete", encoding="utf-8")
    with pytest.raises(ValueError):
        fill(folder, None)
    assert (folder / "kept.txt").exists()


@pytest.mark.parametrize("rooted, kept", [
    (True, ".skilleval/results/evals/a.eval.yml/refactor-skill"), (False, "evals/.skilleval/results/a.eval.yml/refactor-skill"),
], ids=["the project root", "no root"])
def test_results_are_kept_in_the_project_root_or_beside_a_test_file_declaring_none(
    project: Project, rooted: bool, kept: str
) -> None:
    assert results(project.root / "evals/a.eval.yml", project.root if rooted else None, "refactor-skill") == project.root / kept
    assert list(project.root.rglob(".skilleval")) == []


def test_results_give_every_id_a_folder_of_its_own_that_climbs_nowhere(project: Project) -> None:
    ids = ["", ".", "..", "...", "a/b", "a%2Fb", "a\\b", "/", "\\", "%", "a b", "é", "../a", "a/..", "~", "a\0b"]
    kept = {test_id: results(project.root / "evals/a.eval.yml", project.root, test_id) for test_id in ids}
    assert {folder.parent for folder in kept.values()} == {project.root / ".skilleval/results/evals/a.eval.yml"}
    assert all(folder.name not in (".", "..") for folder in kept.values())
    assert len({folder.name for folder in kept.values()}) == len(ids)
    names = {"": "%", ".": "%2E", "..": "%2E%2E", "...": "...", "a/b": "a%2Fb", "a\\b": "a%5Cb", "a\0b": "a%00b", "é": "é"}
    assert {test_id: kept[test_id].name for test_id in names} == names  # readable: only what a folder name cannot hold is encoded


@pytest.mark.parametrize("rooted, folder", [(True, ".skilleval"), (False, "evals/.skilleval")], ids=["the project root", "no root"])
def test_home_is_the_skilleval_folder_of_the_project_root_or_beside_a_test_file_declaring_none(
    project: Project, rooted: bool, folder: str
) -> None:
    assert home(project.root / "evals/a.eval.yml", project.root if rooted else None) == project.root / folder
    assert list(project.root.rglob(".skilleval")) == []


@pytest.mark.parametrize("kept", [{}, {"results/evals/a.eval.yml/t/conversation.jsonl": "1\n"}], ids=["missing", "holding results"])
def test_ignore_creates_the_folder_when_missing_and_has_git_ignore_it_whole_leaving_what_it_holds(
    project: Project, kept: dict[str, str]
) -> None:
    for path, text in kept.items():
        project.write(f".skilleval/{path}", text)
    ignore(project.root / ".skilleval")
    found = tree(project.root / ".skilleval")
    assert "*" in found.pop(".gitignore").splitlines()
    assert found == kept
