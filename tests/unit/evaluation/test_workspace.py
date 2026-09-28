"""`skilleval.evaluation.workspace`: where a test's workspace is and how it is filled."""

import os
import subprocess
import sys
import tempfile

import pytest
from conftest import Project, tree

from skilleval.evaluation.workspace import fill, locate

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
