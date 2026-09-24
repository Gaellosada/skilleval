"""`run_check` on every constraint, per specs/static-checking.md."""

import pytest

from skilleval.static import CheckResult, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check

AT_LEAST_ONCE = {"min": 1, "max": None}
FRONTMATTER = "---\nname: x\n---\nhello"  # 5 words, 4 lines


def run(name: str, params: dict, text: str, severity: str = "error") -> CheckResult:
    check = Check(name, params, severity)
    result = run_check(check, Prompt(text))
    assert result.check == check
    return result


def contains(words: list[str], occurrences: dict | None = AT_LEAST_ONCE, case_sensitive: bool = False) -> dict:
    params = {"words": words, "case_sensitive": case_sensitive}
    if occurrences is not None:
        params["occurrences"] = occurrences
    return params


# words / lines


@pytest.mark.parametrize(("text", "bound", "status"), [
    ("a b c", {"min": None, "max": 3}, "passed"),
    ("a b c", {"min": None, "max": 2}, "failed"),
    ("a b c", {"min": 3, "max": None}, "passed"),
    ("a b c", {"min": 4, "max": None}, "failed"),
    ("a b c", {"min": 3, "max": 3}, "passed"),
    ("a  b\n\n c\t d", {"min": 4, "max": 4}, "passed"),
    ("", {"min": None, "max": 0}, "passed"),
    ("", {"min": 1, "max": None}, "failed"),
    (FRONTMATTER, {"min": None, "max": 5}, "passed"),
    (FRONTMATTER, {"min": None, "max": 4}, "failed"),
])
def test_words_bounds_len_of_split(text: str, bound: dict, status: str) -> None:
    result = run("words", bound, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "bound", "status"), [
    ("a\nb\nc", {"min": None, "max": 3}, "passed"),
    ("a\nb\nc", {"min": None, "max": 2}, "failed"),
    ("a\nb\nc", {"min": 3, "max": None}, "passed"),
    ("a\nb\nc", {"min": 4, "max": None}, "failed"),
    ("a\nb\nc\n", {"min": 3, "max": 3}, "passed"),
    ("a\r\nb", {"min": 2, "max": 2}, "passed"),
    ("a\n\nb", {"min": 3, "max": 3}, "passed"),
    ("", {"min": None, "max": 0}, "passed"),
    ("", {"min": 1, "max": None}, "failed"),
    (FRONTMATTER, {"min": 4, "max": 4}, "passed"),
])
def test_lines_bounds_len_of_splitlines(text: str, bound: dict, status: str) -> None:
    result = run("lines", bound, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


# contains


@pytest.mark.parametrize(("text", "status"), [
    ("Usage: run it", "passed"),
    ("see usage below", "passed"),
    ("Usages vary", "failed"),
    ("reUsage", "failed"),
    ("", "failed"),
])
def test_contains_matches_whole_words_case_insensitively(text: str, status: str) -> None:
    result = run("contains", contains(["Usage"]), text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "status"), [
    ("Usage: run it", "passed"),
    ("see usage below", "failed"),
])
def test_contains_case_sensitive(text: str, status: str) -> None:
    result = run("contains", contains(["Usage"], case_sensitive=True), text)
    assert result.status == status


@pytest.mark.parametrize(("text", "status"), [
    ("run pytest -q now", "passed"),
    ("run -q pytest now", "failed"),
])
def test_contains_multi_word_entry_is_a_phrase(text: str, status: str) -> None:
    result = run("contains", contains(["pytest -q"]), text)
    assert result.status == status


@pytest.mark.parametrize(("occurrences", "status"), [
    ({"min": None, "max": 3}, "failed"),
    ({"min": None, "max": 4}, "passed"),
    ({"min": 4, "max": None}, "passed"),
    ({"min": 5, "max": None}, "failed"),
    ({"min": 4, "max": 4}, "passed"),
    ({"min": 3, "max": 3}, "failed"),
])
def test_contains_occurrences_bound_each_word(occurrences: dict, status: str) -> None:
    result = run("contains", contains(["Usage"], occurrences), "Usage usage USAGE Usage:")
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


def test_contains_occurrences_finding_names_the_one_word_out_of_bounds() -> None:
    result = run("contains", contains(["Usage", "Examples"], {"min": 1, "max": 3}), "Usage Examples Examples Examples Examples")
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == 1
    assert "Examples" in messages[0]


def test_contains_one_finding_per_failing_word() -> None:
    result = run("contains", contains(["Usage", "Examples", "Notes"]), "Usage only")
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == 2
    assert [m for m in messages if "Examples" in m], messages
    assert [m for m in messages if "Notes" in m], messages


# contains_any


@pytest.mark.parametrize(("text", "status"), [
    ("we run pytest", "passed"),
    ("test and tests and pytest", "passed"),
    ("nothing here", "failed"),
    ("tested", "failed"),
])
def test_contains_any_needs_one_of_the_words(text: str, status: str) -> None:
    result = run("contains_any", contains(["test", "tests", "pytest"]), text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "occurrences", "status"), [
    ("test and pytest", {"min": 2, "max": None}, "passed"),
    ("test only", {"min": 2, "max": None}, "failed"),
    ("test tests pytest", {"min": None, "max": 2}, "failed"),
    ("test tests", {"min": None, "max": 2}, "passed"),
    ("test tests pytest", {"min": 3, "max": 3}, "passed"),
])
def test_contains_any_occurrences_bound_the_total(text: str, occurrences: dict, status: str) -> None:
    result = run("contains_any", contains(["test", "tests", "pytest"], occurrences), text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


# contains_none


@pytest.mark.parametrize(("text", "findings"), [
    ("all clean", 0),
    ("a TODO here", 1),
    ("a todo here", 1),
    ("TODOs are fine", 0),
    ("a TODO and a fixme", 2),
    ("TODO TODO", 1),
])
def test_contains_none_one_finding_per_banned_word_found(text: str, findings: int) -> None:
    result = run("contains_none", contains(["TODO", "FIXME"], None), text)
    assert result.status == ("failed" if findings else "passed")
    messages = [f.message for f in result.findings]
    assert len(messages) == findings


def test_contains_none_case_sensitive() -> None:
    result = run("contains_none", contains(["TODO"], None, case_sensitive=True), "a todo here")
    assert result.status == "passed"
    assert result.findings == ()


# matches


@pytest.mark.parametrize(("text", "status"), [
    ("intro\n## Usage\n", "passed"),
    ("## Usage", "passed"),
    ("intro\n## usage\n", "failed"),
    ("intro ## Usage", "failed"),
    ("", "failed"),
])
def test_matches_applies_multiline_patterns_without_case_folding(text: str, status: str) -> None:
    result = run("matches", {"patterns": ["^## [A-Z]"], "occurrences": AT_LEAST_ONCE}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("occurrences", "status"), [
    ({"min": 2, "max": 2}, "passed"),
    ({"min": 3, "max": 3}, "failed"),
    ({"min": None, "max": 1}, "failed"),
])
def test_matches_occurrences_are_non_overlapping(occurrences: dict, status: str) -> None:
    result = run("matches", {"patterns": ["aa"], "occurrences": occurrences}, "aaaa")
    assert result.status == status


def test_matches_folds_case_only_with_an_inline_flag() -> None:
    result = run("matches", {"patterns": ["(?i)^## usage"], "occurrences": AT_LEAST_ONCE}, "## Usage")
    assert result.status == "passed"
    assert result.findings == ()


def test_matches_one_finding_per_failing_pattern() -> None:
    params = {"patterns": ["^## [A-Z]", "TODO", "FIXME"], "occurrences": AT_LEAST_ONCE}
    result = run("matches", params, "## Usage")
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == 2
    assert [m for m in messages if "TODO" in m], messages
    assert [m for m in messages if "FIXME" in m], messages


# matches_any


@pytest.mark.parametrize(("text", "status"), [
    ("uv run x", "passed"),
    ("pytest -q", "passed"),
    ("Pytest -q", "failed"),
    ("nothing", "failed"),
])
def test_matches_any_needs_one_of_the_patterns(text: str, status: str) -> None:
    params = {"patterns": ["pytest -q", "uv run"], "occurrences": AT_LEAST_ONCE}
    result = run("matches_any", params, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "occurrences", "status"), [
    ("pytest -q and uv run", {"min": 2, "max": None}, "passed"),
    ("pytest -q", {"min": 2, "max": None}, "failed"),
    ("pytest -q and uv run and uv run", {"min": None, "max": 2}, "failed"),
])
def test_matches_any_occurrences_bound_the_total(text: str, occurrences: dict, status: str) -> None:
    params = {"patterns": ["pytest -q", "uv run"], "occurrences": occurrences}
    result = run("matches_any", params, text)
    assert result.status == status


# matches_none


@pytest.mark.parametrize(("text", "findings"), [
    ("all clean", 0),
    ("todo", 0),
    ("a TODO here", 1),
    ("FIXME and TODO", 2),
    ("TODO TODO", 1),
])
def test_matches_none_one_finding_per_matching_pattern(text: str, findings: int) -> None:
    result = run("matches_none", {"patterns": ["TODO", "FIXME"]}, text)
    assert result.status == ("failed" if findings else "passed")
    messages = [f.message for f in result.findings]
    assert len(messages) == findings


# paths


@pytest.mark.parametrize(("style", "text", "status"), [
    ("posix", "see src/main.py", "passed"),
    ("posix", "see src\\main.py", "failed"),
    ("windows", "see src\\main.py", "passed"),
    ("windows", "see src/main.py", "failed"),
])
def test_paths_style_fails_on_the_other_convention(style: str, text: str, status: str) -> None:
    result = run("paths", {"style": style}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "detected"), [
    ("see src/main.py", ("src/main.py",)),
    ("", ()),
])
def test_paths_detected_lists_every_path_seen(text: str, detected: tuple[str, ...]) -> None:
    result = run("paths", {}, text)
    assert result.status == "passed"
    assert result.findings == ()
    assert result.detected == detected


@pytest.mark.parametrize(("bound", "status"), [
    ({"min": None, "max": 2}, "passed"),
    ({"min": None, "max": 1}, "failed"),
    ({"min": 2, "max": None}, "passed"),
    ({"min": 3, "max": None}, "failed"),
])
def test_paths_count_bounds_the_paths(bound: dict, status: str) -> None:
    result = run("paths", {"count": bound}, "see src/a.py and src/b.py")
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "excepted", "status"), [
    ("see path/to/file.py", ["path/to/*"], "passed"),
    ("see path/to/a/b.py", ["path/to/*"], "failed"),
    ("see path/to/a/b.py", ["path/to/**"], "passed"),
    ("see <path/to/file.py>", ["<**>"], "passed"),
    ("see path/to/file.py", ["<**>"], "failed"),
    ("see src/a.py and path/to/file.py", ["path/to/*"], "failed"),
])
def test_paths_count_applies_after_except(text: str, excepted: list[str], status: str) -> None:
    result = run("paths", {"count": {"min": None, "max": 0}, "except": excepted}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


def test_paths_except_keeps_excepted_tokens_in_detected() -> None:
    result = run("paths", {"except": ["path/to/*"]}, "see src/a.py and path/to/file.py")
    assert result.status == "passed"
    assert result.findings == ()
    assert result.detected == ("src/a.py", "path/to/file.py")


def test_paths_style_ignores_excepted_paths() -> None:
    result = run("paths", {"style": "windows", "except": ["src/*"]}, "see src/a.py and C:\\x.py")
    assert result.status == "passed"
    assert result.findings == ()


# urls


@pytest.mark.parametrize(("bound", "status"), [
    ({"min": None, "max": 0}, "failed"),
    ({"min": None, "max": 1}, "passed"),
    ({"min": 2, "max": None}, "failed"),
    ({"min": 1, "max": 1}, "passed"),
])
def test_urls_count_bounds_the_urls(bound: dict, status: str) -> None:
    result = run("urls", {"count": bound}, "see https://example.com")
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)
    assert result.detected == ("https://example.com",)


@pytest.mark.parametrize(("text", "detected"), [
    ("a https://a.com and http://b.com/x", ("https://a.com", "http://b.com/x")),
    ("", ()),
])
def test_urls_detected_lists_every_url(text: str, detected: tuple[str, ...]) -> None:
    result = run("urls", {}, text)
    assert result.status == "passed"
    assert result.detected == detected


@pytest.mark.parametrize(("url", "status"), [
    ("https://docs.anthropic.com/x", "passed"),
    ("https://api.docs.anthropic.com/x", "passed"),
    ("https://DOCS.Anthropic.COM/x", "passed"),
    ("https://user:pw@docs.anthropic.com:8443/x", "passed"),
    ("https://notdocs.anthropic.com/x", "failed"),
    ("https://example.com/docs.anthropic.com", "failed"),
    ("https://anthropic.com", "failed"),
])
def test_urls_deny_with_except_is_a_whitelist(url: str, status: str) -> None:
    result = run("urls", {"default": "deny", "except": ["docs.anthropic.com"]}, f"see {url}")
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)
    assert result.detected == (url,)


@pytest.mark.parametrize(("url", "status"), [
    ("http://localhost:8000/", "failed"),
    ("http://api.localhost/", "failed"),
    ("https://example.com", "passed"),
])
def test_urls_allow_with_except_is_a_blacklist(url: str, status: str) -> None:
    result = run("urls", {"default": "allow", "except": ["localhost"]}, f"see {url}")
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


def test_urls_count_and_host_policy_report_together() -> None:
    params = {"count": {"min": None, "max": 1}, "default": "deny", "except": ["docs.anthropic.com"]}
    result = run("urls", params, "see https://bad.com and https://docs.anthropic.com")
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == 2
    assert result.detected == ("https://bad.com", "https://docs.anthropic.com")


def test_urls_one_finding_per_offending_url_with_its_line() -> None:
    text = "see https://bad.com\nok https://docs.anthropic.com\nand https://worse.com"
    result = run("urls", {"default": "deny", "except": ["docs.anthropic.com"]}, text)
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [1, 3]
    assert "https://bad.com" in result.findings[0].message
    assert "https://worse.com" in result.findings[1].message


# code


@pytest.mark.parametrize(("text", "bound", "status"), [
    ("```\nx\n```", {"min": None, "max": 0}, "failed"),
    ("```\nx\n```", {"min": None, "max": 1}, "passed"),
    ("```\nx\n```\n\n```\ny\n```", {"min": None, "max": 1}, "failed"),
    ("```\nx\n```", {"min": 2, "max": None}, "failed"),
    ("```\nx\n```\n\n~~~\ny\n~~~", {"min": 2, "max": 2}, "passed"),
    ("use `x` and ``y``", {"min": None, "max": 0}, "passed"),
    ("", {"min": None, "max": 0}, "passed"),
])
def test_code_count_bounds_fenced_blocks_only(text: str, bound: dict, status: str) -> None:
    result = run("code", {"count": bound}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


@pytest.mark.parametrize(("text", "detected"), [
    ("```bash\nx\n```\n\n```\ny\n```\n\n~~~Python\nz\n~~~", ("bash", "not_specified", "python")),
    ("", ()),
])
def test_code_detected_lists_the_tag_of_every_block(text: str, detected: tuple[str, ...]) -> None:
    result = run("code", {}, text)
    assert result.status == "passed"
    assert result.detected == detected


@pytest.mark.parametrize(("text", "status"), [
    ("```bash\nx\n```", "passed"),
    ("```Bash\nx\n```", "passed"),
    ("```\nx\n```", "passed"),
    ("```python\nx\n```", "failed"),
    ("```sh\nx\n```", "failed"),
])
def test_code_deny_with_except_permits_listed_languages_only(text: str, status: str) -> None:
    result = run("code", {"default": "deny", "except": ["bash", "not_specified"]}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


def test_code_except_entries_match_case_insensitively() -> None:
    result = run("code", {"default": "deny", "except": ["Bash"]}, "```bash\nx\n```")
    assert result.status == "passed"
    assert result.findings == ()


@pytest.mark.parametrize(("text", "status"), [
    ("```bash\nx\n```", "passed"),
    ("```\nx\n```", "failed"),
    ("~~~\nx\n~~~", "failed"),
])
def test_code_allow_with_except_not_specified_requires_a_tag(text: str, status: str) -> None:
    result = run("code", {"default": "allow", "except": ["not_specified"]}, text)
    assert result.status == status
    messages = [f.message for f in result.findings]
    assert len(messages) == (1 if status == "failed" else 0)


def test_code_count_and_language_policy_report_together() -> None:
    params = {"count": {"min": None, "max": 1}, "default": "deny", "except": ["bash"]}
    result = run("code", params, "```python\nx\n```\n\n```bash\ny\n```")
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == 2
    assert result.detected == ("python", "bash")


def test_code_one_finding_per_offending_block_at_its_opening_fence() -> None:
    text = "intro\n\n```python\nx\n```\n\n```bash\ny\n```\n\n```ruby\nz\n```"
    result = run("code", {"default": "deny", "except": ["bash"]}, text)
    assert result.status == "failed"
    assert [f.line for f in result.findings] == [3, 11]
    assert result.detected == ("python", "bash", "ruby")


# detected


@pytest.mark.parametrize(("name", "params"), [
    ("words", {"min": None, "max": 1}),
    ("contains", contains(["Usage"])),
    ("matches", {"patterns": ["^## [A-Z]"], "occurrences": AT_LEAST_ONCE}),
])
def test_non_heuristic_checks_detect_nothing(name: str, params: dict) -> None:
    result = run(name, params, "see src/a.py and https://a.com")
    assert result.status == "failed"
    assert result.detected == ()


# severity


def test_warn_severity_on_a_heuristic_check_keeps_detected() -> None:
    result = run("urls", {"count": {"min": None, "max": 0}}, "see https://example.com", severity="warn")
    assert result.status == "warned"
    assert result.detected == ("https://example.com",)
