"""The workspace: the folder the model works in. Specified in specs/evaluations.md, under
`working_folder`."""

from pathlib import Path


def locate(file: Path, test_id: str) -> Path:
    """The workspace of the test `test_id` of the test file `file`: the same folder every time
    for the same test, its own for every test, in the system's temporary directory under a
    folder skilleval uses alone. The model can read both names, so neither says anything of
    skilleval or of the test. Creates nothing."""
    raise NotImplementedError


def fill(folder: Path, working_folder: Path | None) -> None:
    """Empty the workspace `folder`, created when missing, and copy the contents of
    `working_folder` into it, itself left as it is; None leaves the workspace empty."""
    raise NotImplementedError
