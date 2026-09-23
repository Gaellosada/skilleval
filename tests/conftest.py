"""Shared fixture: a scratch project on disk, with the cwd inside it."""

from __future__ import annotations

import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from skilleval.cli import main
from skilleval.testfile import TestFile, load


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
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Project:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'scratch'\n")
    monkeypatch.chdir(tmp_path)
    return Project(tmp_path, capsys)
