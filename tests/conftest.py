"""Shared fixture: a scratch project on disk, with the cwd inside it."""

import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from skilleval.cli import main
from skilleval.testfile import TestFile, load

todo = pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="structured, not implemented yet")


def tree(folder: Path) -> dict[str, str]:
    """The files below `folder`, each posix path relative to it with its text."""
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8") for p in folder.rglob("*") if p.is_file()}


@pytest.fixture(autouse=True)
def no_harness(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """`PATH` holds one empty directory: no test finds a program, so none ever starts a harness."""
    monkeypatch.setenv("PATH", str(tmp_path_factory.mktemp("path")))


@dataclass
class Project:
    """A directory holding a `pyproject.toml` marker; every path is relative to it."""

    root: Path
    capsys: pytest.CaptureFixture[str]

    def write(self, relpath: str, text: str = "") -> Path:
        """Write a file (parents created, text dedented) and return its path."""
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def copy(self, fixture: Path) -> None:
        """Copy a fixture directory's contents into the project."""
        shutil.copytree(fixture, self.root, dirs_exist_ok=True)

    def load(self, relpath: str) -> TestFile:
        return load(self.root / relpath)

    def tests(self, body: str, path: str = "evals/a.eval.yml") -> str:
        """Write a test file declaring `root: pyproject.toml` and the given `tests:` entries; return its path."""
        self.write(path, "root: pyproject.toml\ntests:\n" + textwrap.indent(textwrap.dedent(body), "  "))
        return path

    def cli(self, *args: str) -> tuple[int, str]:
        """Run `main` and return its exit code and everything it printed to stdout."""
        self.capsys.readouterr()
        code = main(list(args))
        return code, self.capsys.readouterr().out


@pytest.fixture
def project(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Project:
    """The project, with a system temporary directory of its own beside it, for the workspaces."""
    root = tmp_path_factory.mktemp("project")
    (root / "pyproject.toml").write_text("[project]\nname = 'scratch'\n", encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("tmp")))
    return Project(root, capsys)
