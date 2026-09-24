"""`skilleval.testfile.paths`: `find_root`, `resolve` and `glob_to_regex` directly. Path
resolution as `load` applies it is in test_load.py."""

from pathlib import Path

import pytest

from skilleval.testfile.paths import find_root, glob_to_regex, resolve

# find_root


def test_find_root_marker_file(project):
    project.write("sub/marker")
    assert find_root(project.write("sub/deep/t.eval.yml"), "marker") == project.root / "sub"


def test_find_root_marker_directory(project):
    (project.root / "sub" / ".git").mkdir(parents=True)
    assert find_root(project.write("sub/deep/t.eval.yml"), ".git") == project.root / "sub"


def test_find_root_nearest_ancestor_wins(project):
    project.write("sub/pyproject.toml")
    assert find_root(project.write("sub/deep/t.eval.yml"), "pyproject.toml") == project.root / "sub"


def test_find_root_marker_absent_is_file_not_found(project):
    with pytest.raises(FileNotFoundError):
        find_root(project.write("t.eval.yml"), "no-such-marker.xyz")


# resolve

FILE = Path("/p/evals/t.eval.yml")
ROOT = Path("/p")


def test_resolve_dot_slash_from_the_file_directory():
    assert resolve("./x", FILE, ROOT) == Path("/p/evals/x")


def test_resolve_dot_slash_needs_no_root():
    assert resolve("./x", FILE, None) == Path("/p/evals/x")


@pytest.mark.parametrize("written, root, expected", [
    ("x", ROOT, "/p/x"),
    ("../x", ROOT, "/x"),
    ("/abs/x", ROOT, "/abs/x"),
    ("/abs/x", None, "/abs/x"),
], ids=["root-relative", "parent of root", "absolute", "absolute without root"])
def test_resolve_other_path_from_root(written: str, root: Path | None, expected: str):
    assert resolve(written, FILE, root) == Path(expected)


def test_resolve_root_relative_path_without_root_is_a_value_error():
    with pytest.raises(ValueError):
        resolve("x", FILE, None)


# glob_to_regex


@pytest.mark.parametrize("pattern, token, expected", [
    ("*.md", "a.md", True),
    ("*.md", "dir/a.md", False),
    ("a?c", "abc", True),
    ("a?c", "a/c", False),
    ("a?c", "ac", False),
    ("[ab].md", "a.md", True),
    ("[ab].md", "c.md", False),
    ("[ab].md", "/.md", False),
    ("**", "a/b/c.md", True),
    ("**/fixtures/**", "a/b/fixtures/c.md", True),
    ("**/fixtures/**", "fixtures/c.md", True),
    ("**/fixtures/**", "a/fixturesx/c.md", False),
    ("**/SKILL.md", ".claude/skills/refactor/SKILL.md", True),
    ("<*>", "<file>", True),
    ("a.md", "a.md", True),
    ("a.md", "axmd", False),
    ("a.md", "xa.md", False),
    ("a.md", "a.mdx", False),
])
def test_glob_to_regex(pattern, token, expected):
    assert bool(glob_to_regex(pattern).search(token)) is expected
