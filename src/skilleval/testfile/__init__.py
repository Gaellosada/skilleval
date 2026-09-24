"""A test file (`*.eval.yml`) read into dataclasses. Specified in specs/README.md.

Every rule about what a file may contain is enforced here, so a bad file fails at load time
with a `LoadError` and nothing downstream validates again. `schema` holds the dataclasses,
`checks` reads check entries, `templates` reads `uses`, `paths` resolves paths.
"""

from pathlib import Path

from skilleval.testfile.checks import Check
from skilleval.testfile.schema import (
    FilePrompt,
    GlobPrompt,
    LoadError,
    PromptSpec,
    Test,
    TestFile,
    TextPrompt,
)

__all__ = [
    "Check", "FilePrompt", "GlobPrompt", "LoadError", "PromptSpec", "Test", "TestFile",
    "TextPrompt", "load",
]

KINDS = frozenset({"static-check"})


def load(path: Path) -> TestFile:
    """Read one file, resolve its `uses` and paths, validate everything. Raises `LoadError`.

    A key repeated in any mapping is an error, where PyYAML would silently keep the last one:
    the document is composed as a node tree (`yaml.compose`) and walked, building the
    values and their dotted keys together.
    """
    raise NotImplementedError
