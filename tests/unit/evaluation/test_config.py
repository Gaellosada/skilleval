"""`skilleval.evaluation.config.load`: the settings file, written when missing, its keys, the
credentials read from the environment, and its errors. Specified in specs/config.md."""

import stat
from contextlib import suppress
from pathlib import Path

import pytest
import yaml
from conftest import tree

from skilleval.evaluation.config import CREDENTIALS, Config, load
from skilleval.testfile import LoadError

KEY, TOKEN = "sk-ant-api03-key", "sk-ant-oat01-token"
SECRET = "SECRETVALUE"  # of a credential written wrongly, which no error shows


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "config.yml"


def test_a_missing_settings_file_is_written_in_a_folder_git_ignores_with_the_default_backend_and_the_credentials_as_comments(
    tmp_path: Path
) -> None:
    path = tmp_path / ".skilleval/config.yml"
    assert load(path) == Config(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600  # its user's alone to read
    assert "*" in (path.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    text = path.read_text(encoding="utf-8")
    assert yaml.safe_load(text) == {"backend": "claude_cli"}
    comments = [line for line in text.splitlines() if line.lstrip().startswith("#")]
    assert all(any(name in comment for comment in comments) for name in CREDENTIALS)


@pytest.mark.parametrize("text", ["backend: claude_api\n", "backend: claude_web\n"], ids=["read", "an error"])
def test_a_settings_file_that_exists_is_never_written_again(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o640)
    with suppress(LoadError):
        load(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    found = tree(path.parent)
    assert "*" in found.pop(".gitignore").splitlines()  # ignored by git, even written by hand
    assert found == {"config.yml": text}


def test_a_default_settings_file_that_cannot_be_written_is_an_os_error_once_git_ignores_its_folder(path: Path) -> None:
    path.symlink_to(path.parent / "nowhere/config.yml")
    with pytest.raises(OSError):
        load(path)
    assert "*" in (path.parent / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("text, fields", [
    ("backend: claude_cli\n", {}),
    ("backend: claude_api\n", {"backend": "claude_api"}),
    (f"backend: claude_cli\nANTHROPIC_API_KEY: {KEY}\nCLAUDE_CODE_OAUTH_TOKEN: {TOKEN}\n",
     {"anthropic_api_key": KEY, "claude_code_oauth_token": TOKEN}),
    (f"backend: ' claude_api '\nCLAUDE_CODE_OAUTH_TOKEN: '  {TOKEN}  '\n", {"backend": "claude_api", "claude_code_oauth_token": TOKEN}),
], ids=["claude_cli", "claude_api", "both credentials", "without the spaces around them"])
def test_every_key_is_read(path: Path, text: str, fields: dict[str, str]) -> None:
    path.write_text(text, encoding="utf-8")
    assert load(path) == Config(path, **fields)


@pytest.mark.parametrize("written, environment, read", [
    (None, "from-the-environment", "from-the-environment"),
    ("from-the-file", "from-the-environment", "from-the-file"),
    (None, "", None),
    (None, " \t", None),
], ids=["not written: the environment", "written in both: the file wins", "an empty variable: none", "a blank variable: none"])
@pytest.mark.parametrize("name", CREDENTIALS)
def test_a_credential_the_file_does_not_write_is_read_from_the_environment_variable_of_its_name(
    path: Path, monkeypatch: pytest.MonkeyPatch, name: str, written: str | None, environment: str, read: str | None
) -> None:
    path.write_text("backend: claude_cli\n" + (f"{name}: {written}\n" if written else ""), encoding="utf-8")
    monkeypatch.setenv(name, environment)
    assert getattr(load(path), name.lower()) == read


@pytest.mark.parametrize("content, key", [
    (b"backend: caf\xe9\n", ""),
    (b"backend: [claude_cli\n", ""),
    (b"backend: " + b"[" * 3000 + b"]" * 3000 + b"\n", ""),
    (b"- backend: claude_cli\n", ""),
    (b"claude_cli\n", ""),
    (b"", ""),
    (b"# backend: claude_cli\nANTHROPIC_API_KEY: sk-ant-api03-key\n", "backend"),
    (b"backend: claude_web\n", "backend"),
    (b"backend: [claude_cli]\n", "backend"),
    (b"backend:\n", "backend"),
    (b"backend: claude_cli\nmodel: claude-sonnet-5\n", ""),
    (b"backend: claude_cli\nbackend: claude_api\n", "backend"),
    (b"backend: claude_cli\nANTHROPIC_API_KEY: 3\n", "ANTHROPIC_API_KEY"),
    (b"backend: claude_cli\nANTHROPIC_API_KEY:\n", "ANTHROPIC_API_KEY"),
    (b"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: ''\n", "CLAUDE_CODE_OAUTH_TOKEN"),
    (b"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: ' \t'\n", "CLAUDE_CODE_OAUTH_TOKEN"),
], ids=["not UTF-8", "not YAML", "nested too deep", "a list", "a scalar", "an empty file", "no backend", "a backend of neither kind",
        "a backend that is not text", "a backend left empty", "an unknown key, never shown", "a key written twice", "a credential that is not text",
        "a credential left empty", "an empty credential", "a blank credential"])
def test_settings_that_cannot_be_used_are_a_load_error_naming_the_file_and_the_key(
    path: Path, content: bytes, key: str
) -> None:
    path.write_bytes(content)
    with pytest.raises(LoadError) as info:
        load(path)
    assert (info.value.path, info.value.key) == (path, key)


@pytest.mark.parametrize("text", [
    f"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-{SECRET}: x\n",
    f'backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: "sk-ant-oat01-{SECRET}\n',
    f"backend: claude_cli\nsk-ant-oat01-{SECRET}: 1\n",
    f"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-{SECRET}\nCLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-{SECRET}\n",
    f"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: {{a: sk-ant-oat01-{SECRET}}}\n",
    f"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: [sk-ant-oat01-{SECRET}]\n",
    f"backend: sk-ant-oat01-{SECRET}\n",
    f"backend: claude_cli\nCLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-{SECRET}\xe9\n",
], ids=["a YAML error on its line", "an unclosed quote", "written as a key", "written twice", "in a mapping", "in a list",
        "as the backend", "holding a byte that is not UTF-8"])
def test_an_error_of_the_settings_never_shows_a_credential_written_wrongly(path: Path, text: str) -> None:
    path.write_bytes(text.encode("latin-1"))  # the é of the last case is the byte 0xe9, which UTF-8 cannot read
    with pytest.raises(LoadError) as info:
        load(path)
    assert SECRET not in str(info.value) and "0xe9" not in str(info.value)


def test_a_config_never_shows_its_credentials_and_still_compares_them(path: Path) -> None:
    config = Config(path, anthropic_api_key=KEY, claude_code_oauth_token=TOKEN)
    assert KEY not in repr(config) and TOKEN not in repr(config)
    assert config != Config(path, anthropic_api_key=KEY) and config != Config(path, claude_code_oauth_token=TOKEN)
