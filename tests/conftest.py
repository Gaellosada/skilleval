"""Shared fixture: a scratch project on disk, with the cwd inside it."""

import os
import shutil
import tempfile
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

from skilleval.cli import main
from skilleval.evaluation.config import CREDENTIALS
from skilleval.testfile import TestFile, load

FILE = "evals/a.eval.yml"  # the test file most tests write


def tree(folder: Path) -> dict[str, str]:
    """The files below `folder`, each posix path relative to it with its text."""
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8") for p in folder.rglob("*") if p.is_file()}


@pytest.fixture(autouse=True)
def no_harness(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """`PATH` holds one empty directory: no test finds a program, so none ever starts a harness.
    Claude Code's configuration is another, so none reads the skills of whoever runs the tests,
    and the credential variables are unset, so none reads their credentials. The system's
    temporary directory is a scratch one, so the workspaces go there and nowhere else."""
    monkeypatch.setenv("PATH", str(tmp_path_factory.mktemp("path")))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("tmp")))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("configuration")))
    for credential in CREDENTIALS:
        monkeypatch.delenv(credential, raising=False)


TOOLS = ("bash", "cat", "grep", "head", "mkdir", "rm", "seq", "sleep", "touch", "tr")  # what the `run` commands of the tests call


@pytest.fixture
def bash(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """`PATH` also holds a directory of links to the system's `bash` and the `TOOLS` the
    tests' `run` commands call, and nothing else, so a harness stays out of reach."""
    tools = tmp_path_factory.mktemp("tools")
    for tool in TOOLS:
        found = shutil.which(tool, path=os.defpath)
        assert found is not None, f"the tests of `run` need {tool} in {os.defpath}"
        (tools / tool).symlink_to(found)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """How many times each file, by name, is read as text from here on."""
    counted: Counter[str] = Counter()
    read_text = Path.read_text

    def counting(self: Path, *args: object, **kwargs: object) -> str:
        counted[self.name] += 1
        return read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting)
    return counted


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

    def tests(self, body: str, path: str = FILE) -> str:
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
    """The project, the cwd inside it."""
    root = tmp_path_factory.mktemp("project")
    (root / "pyproject.toml").write_text("[project]\nname = 'scratch'\n", encoding="utf-8")
    monkeypatch.chdir(root)
    return Project(root, capsys)
