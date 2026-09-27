"""`skilleval.evaluation.workspace`: where a test's workspace is and how it is filled."""

import tempfile

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


@pytest.mark.parametrize("stale", [True, False], ids=["emptied", "created"])
@pytest.mark.parametrize("seed", [{"pkg/utils.py": "x = 1\n", ".claude/settings.json": "{}"}, {}], ids=["filled", "left empty"])
def test_fill_leaves_in_the_workspace_the_contents_of_the_working_folder_and_nothing_else(
    project: Project, stale: bool, seed: dict[str, str]
) -> None:
    folder, working_folder = project.root / "workspace", project.root / "fixtures/utils" if seed else None
    for path, text in seed.items():
        project.write(f"fixtures/utils/{path}", text)
    if stale:
        project.write("workspace/sub/stale.txt", "left by the run before")
    fill(folder, working_folder)
    assert folder.is_dir() and tree(folder) == seed
    assert working_folder is None or tree(working_folder) == seed
