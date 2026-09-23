"""`skilleval.testfile.paths`: `find_root`, `resolve` and `glob_to_regex` directly, and
path resolution as `load` applies it."""

from __future__ import annotations

from pathlib import Path

import pytest

from skilleval.testfile import FilePrompt, LoadError, load
from skilleval.testfile.paths import find_root, glob_to_regex, resolve

STATIC = """
    tests:
      skills:
        kind: static-check
        prompt: {text: hi}
"""


def load_error(path: Path) -> LoadError:
    with pytest.raises(LoadError) as info:
        load(path)
    return info.value


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


@pytest.mark.parametrize("written, expected", [
    ("x", "/p/x"),
    ("../x", "/x"),
    ("/abs/x", "/abs/x"),
])
def test_resolve_other_path_from_root(written: str, expected: str):
    assert resolve(written, FILE, ROOT) == Path(expected)


def test_resolve_root_relative_path_without_root_is_a_value_error():
    with pytest.raises(ValueError):
        resolve("x", FILE, None)


# Path resolution through load


def test_dot_slash_path_is_relative_to_the_test_file(project):
    t = load(project.write("sub/t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: ./SKILL.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "sub" / "SKILL.md")


def test_other_path_is_relative_to_the_project_root(project):
    t = load(project.write("sub/t.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """)).tests["skills"]
    assert t.prompt == FilePrompt(project.root / "SKILL.md")


def test_root_is_the_nearest_ancestor_holding_the_marker_file(project):
    project.write("sub/pyproject.toml")
    tf = load(project.write("sub/deep/t.eval.yml", """
        root: pyproject.toml
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """))
    assert tf.root == project.root / "sub"
    assert tf.tests["skills"].prompt == FilePrompt(project.root / "sub" / "SKILL.md")


def test_root_may_be_the_test_file_own_directory(project):
    project.write("sub/pyproject.toml")
    tf = load(project.write("sub/t.eval.yml", STATIC + "    root: pyproject.toml\n"))
    assert tf.root == project.root / "sub"


def test_root_marker_may_be_a_directory(project):
    (project.root / "sub" / ".git").mkdir(parents=True)
    tf = load(project.write("sub/deep/t.eval.yml", STATIC + "    root: .git\n"))
    assert tf.root == project.root / "sub"


def test_root_marker_never_found_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", STATIC + "    root: no-such-marker.xyz\n"))
    assert e.key == "root"
    assert "no-such-marker.xyz" in e.message


def test_root_relative_path_without_root_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt: SKILL.md
    """))
    assert e.key == "tests.skills.prompt"
    assert "SKILL.md" in e.message


def test_root_relative_include_without_root_is_a_load_error(project):
    e = load_error(project.write("t.eval.yml", """
        tests:
          skills:
            kind: static-check
            prompt:
              include: skills/**/SKILL.md
    """))
    assert e.key == "tests.skills.prompt.include"
    assert "skills/**/SKILL.md" in e.message


# glob_to_regex


@pytest.mark.parametrize("pattern, token, expected", [
    ("*.md", "a.md", True),
    ("*.md", "dir/a.md", False),
    ("path/to/*", "path/to/a/b.py", False),
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
    ("**/SKILL.md", "SKILL.md", True),
    ("**/SKILL.md", ".claude/skills/refactor/SKILL.md", True),
    ("<*>", "<file>", True),
    ("a/**/b", "a/b", True),
    ("a.md", "a.md", True),
    ("a.md", "axmd", False),
    ("a.md", "xa.md", False),
    ("a.md", "a.mdx", False),
])
def test_glob_to_regex(pattern, token, expected):
    assert bool(glob_to_regex(pattern).search(token)) is expected
