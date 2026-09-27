"""`skilleval.evaluation.workspace`: where a test's workspace is and how it is filled."""

import tempfile
from pathlib import Path

import pytest
from conftest import Project, todo, tree

from skilleval.evaluation.workspace import fill, locate

pytestmark = todo


def test_the_same_test_always_gets_the_same_folder_and_every_test_its_own(project: Project) -> None:
    a, b = project.root / "evals/a.eval.yml", project.root / "evals/b.eval.yml"
    assert locate(a, "t") == locate(a, "t")
    assert len({locate(a, "t"), locate(a, "u"), locate(b, "t")}) == 3


def test_workspace_is_in_the_temporary_directory_under_names_that_say_nothing(project: Project) -> None:
    folder = locate(project.root / "evals/refactor.eval.yml", "split-utils")
    shared, own = folder.relative_to(tempfile.gettempdir()).parts
    assert not any(word in (shared + own).lower() for word in ("skilleval", "eval", "test", "refactor", "split"))
    assert not folder.is_relative_to(project.root)
    assert not folder.exists()


def test_fill_empties_the_workspace_and_copies_the_working_folder_left_as_it_is(project: Project) -> None:
    project.write("fixtures/utils/pkg/utils.py", "x = 1\n")
    project.write("workspace/stale.txt", "left by the run before")
    fill(project.root / "workspace", project.root / "fixtures/utils")
    assert tree(project.root / "workspace") == tree(project.root / "fixtures/utils") == {"pkg/utils.py": "x = 1\n"}


@pytest.mark.parametrize("stale", [True, False], ids=["emptied", "created"])
def test_fill_without_a_working_folder_leaves_an_empty_workspace(tmp_path: Path, stale: bool) -> None:
    folder = tmp_path / "workspace"
    if stale:
        (folder / "sub").mkdir(parents=True)
        (folder / "sub/stale.txt").write_text("left by the run before")
    fill(folder, None)
    assert folder.is_dir() and not any(folder.iterdir())
