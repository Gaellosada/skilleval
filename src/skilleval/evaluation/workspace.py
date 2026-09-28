"""The workspace: the folder the model works in. Specified in specs/evaluations.md, under
`working_folder`."""

import hashlib
import shutil
import tempfile
from pathlib import Path

SHARED = "w-0f3a9c"  # the folder of the workspaces: the model can read the name, so it says nothing


def locate(file: Path, test_id: str) -> Path:
    """The workspace of the test `test_id` of the test file `file`: the same folder every time
    for the same test, its own for every test, in the system's temporary directory under a
    folder skilleval uses alone. The model can read both names, so neither says anything of
    skilleval or of the test. Creates nothing."""
    name = hashlib.sha256(f"{file}::{test_id}".encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir(), SHARED, name)


def results(file: Path, root: Path | None, test_id: str) -> Path:
    """The folder the results of the test `test_id` of the test file `file` are kept in, in
    the project: `<base>/.skilleval/results/<file relative to base>/<test_id>`, `<base>` being `root`, or the
    directory of `file` when it declares none. The id is percent-encoded into one folder name
    of its own, readable when it is an ordinary one. Creates nothing."""
    raise NotImplementedError


def fill(folder: Path, working_folder: Path | None) -> None:
    """Empty the workspace `folder`, created when missing, then copy into it the contents of
    `working_folder`, which is never modified, a symbolic link as a link; None leaves the
    workspace empty.

    Raises `ValueError`, touching nothing, for a folder that is not directly inside the one
    `locate` puts the workspaces in: only a workspace is ever emptied. Raises `OSError` when
    the copy fails."""
    if folder.parent != Path(tempfile.gettempdir(), SHARED):
        raise ValueError(f"{folder} is not a workspace, and only a workspace is ever emptied")
    if folder.exists():
        shutil.rmtree(folder)
    if working_folder is None:
        folder.mkdir(parents=True)
    else:
        shutil.copytree(working_folder, folder, symlinks=True)
