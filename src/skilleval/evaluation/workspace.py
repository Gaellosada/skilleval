"""The workspace, the folder the model works in, and the results it leaves in the project.
Specified in specs/evaluations.md, under `working_folder`."""

import hashlib
import shutil
import tempfile
from pathlib import Path

from skilleval.testfile.paths import HOME

ESCAPED = {ord(c): f"%{ord(c):02X}" for c in "%/\\\0"}  # what an id cannot hold in a folder name
SHARED = "w-0f3a9c"  # the folder of the workspaces: the model can read the name, so it says nothing


def locate(file: Path, test_id: str) -> Path:
    """The workspace of the test `test_id` of the test file `file`: the same folder every time
    for the same test, its own for every test, in the system's temporary directory under a
    folder skilleval uses alone. The model can read both names, so neither says anything of
    skilleval or of the test. Creates nothing."""
    return Path(tempfile.gettempdir(), SHARED, neutral(f"{file}::{test_id}"))


def neutral(text: str) -> str:
    """A folder name for `text`, the same every time, that says nothing of it."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def results(file: Path, root: Path | None, test_id: str) -> Path:
    """The folder the results of the test `test_id` of the test file `file` are kept in, in
    the project: `<base>/.skilleval/results/<file relative to base>/<test_id>`, `<base>` being
    `root`, or the directory of `file` when it declares none. The id is written as is, but for
    `%`, `/`, `\\` and NUL, percent-encoded, and `""`, `.` and `..`, which would climb, written
    `%`, `%2E` and `%2E%2E`, so each id has one folder name of its own. Creates nothing."""
    name = test_id.translate(ESCAPED)
    name = {"": "%", ".": "%2E", "..": "%2E%2E"}.get(name, name)  # a lone % is what no other id gives
    return home(file, root) / "results" / file.relative_to(root or file.parent) / name


def keep(folder: Path, file: Path, root: Path | None, test_id: str, conversation: str, judges: str) -> None:
    """Replace the `results` of the test `test_id` of `file` with `conversation.jsonl` holding
    `conversation`, `judges.jsonl` holding `judges` unless it is empty, and its workspace
    `folder`, moved to `workspace/` when it exists, in a `home` that git ignores, whatever a
    failure leaves. Raises `OSError` when any of it fails."""
    ignore(home(file, root))
    kept = results(file, root, test_id)
    if kept.exists():
        shutil.rmtree(kept)
    kept.mkdir(parents=True)
    (kept / "conversation.jsonl").write_text(conversation, encoding="utf-8")
    if judges:
        (kept / "judges.jsonl").write_text(judges, encoding="utf-8")
    if folder.exists():
        shutil.move(folder, kept / "workspace")


def home(file: Path, root: Path | None) -> Path:
    """The folder `.skilleval` of the test file `file`: in `root`, or beside the file when it
    declares none. Creates nothing."""
    return (root or file.parent) / HOME


def ignore(folder: Path) -> None:
    """Create `folder`, a `home`, when it is missing, and write its `.gitignore`, holding `*`,
    so that git ignores whatever the folder holds. Raises `OSError`."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".gitignore").write_text("*\n", encoding="utf-8")


def fill(folder: Path, working_folder: Path | None) -> None:
    """Empty the workspace `folder`, created when missing, then copy into it the contents of
    `working_folder`, which is never modified, a symbolic link as a link, and nothing named
    `HOME`, which is skilleval's and may hold credentials; None leaves the workspace empty.

    Raises `ValueError`, touching nothing, for a folder that is not directly inside the one
    `locate` puts the workspaces in: only a workspace is ever emptied, or the folder of a
    judge, which sits beside it and is emptied the same way. Raises `OSError` when the copy
    fails."""
    if folder.parent != Path(tempfile.gettempdir(), SHARED):
        raise ValueError(f"{folder} is not a workspace, and only a workspace is ever emptied")
    if folder.exists():
        shutil.rmtree(folder)
    if working_folder is None:
        folder.mkdir(parents=True)
    else:
        shutil.copytree(working_folder, folder, symlinks=True, ignore=shutil.ignore_patterns(HOME))
