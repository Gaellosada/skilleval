"""`run_check` on the constraints, per specs/static-checking.md: one table per mechanism the checks share."""

import pytest

from skilleval.static import CheckResult, run_check
from skilleval.static.prompt import Prompt
from skilleval.testfile import Check

AT_LEAST_ONCE = {"min": 1, "max": None}
FRONTMATTER = "---\nname: x\n---\nhello"  # 5 words, 4 lines
WHITELIST = {"default": "deny", "except": ["docs.anthropic.com"]}
BLACKLIST = {"default": "allow", "except": ["localhost"]}
SHELL_ONLY = {"default": "deny", "except": ["bash", "not_specified"]}
TAG_REQUIRED = {"default": "allow", "except": ["not_specified"]}
THREE_URLS = "see https://bad.com\nok https://docs.anthropic.com\nand https://worse.com"
THREE_BLOCKS = "intro\n\n```python\nx\n```\n\n```bash\ny\n```\n\n```ruby\nz\n```"


def run(name: str, params: dict, text: str, severity: str = "error") -> CheckResult:
    check = Check(name, params, severity)
    result = run_check(check, Prompt(text))
    assert result.check == check
    return result


# bounds: one comparator behind `words`, `lines` and `count`; a count out of bounds is one finding


@pytest.mark.parametrize(("check", "params", "text", "status"), [
    # the comparator, once: equal to the bound passes, one over or under fails, min = max is exact, empty is 0
    ("words", {"min": None, "max": 3}, "a b c", "passed"),
    ("words", {"min": None, "max": 2}, "a b c", "failed"),
    ("words", {"min": 3, "max": None}, "a b c", "passed"),
    ("words", {"min": 4, "max": None}, "a b c", "failed"),
    ("words", {"min": 3, "max": 3}, "a b c", "passed"),
    ("words", {"min": None, "max": 0}, "", "passed"),
    ("words", {"min": 1, "max": None}, "", "failed"),
    ("lines", {"min": None, "max": 2}, "a\nb\nc", "failed"),
    ("lines", {"min": 1, "max": None}, "", "failed"),
    # what each check counts, pinned with an exact bound
    ("words", {"min": 4, "max": 4}, "a  b\n\n c\t d", "passed"),  # len(text.split())
    ("words", {"min": 5, "max": 5}, FRONTMATTER, "passed"),  # frontmatter included
    ("lines", {"min": 3, "max": 3}, "a\n\nb", "passed"),  # len(text.splitlines()), blanks included
    ("lines", {"min": 3, "max": 3}, "a\nb\nc\n", "passed"),  # a trailing newline adds no line
    ("lines", {"min": 2, "max": 2}, "a\r\nb", "passed"),
    ("lines", {"min": 4, "max": 4}, FRONTMATTER, "passed"),
    ("lines", {"min": 0, "max": 0}, "", "passed"),  # an empty file has 0 lines
    ("paths", {"count": {"min": 2, "max": 2}}, "see src/a.py and src/b.py", "passed"),
    ("urls", {"count": {"min": 1, "max": 1}}, "see https://example.com", "passed"),
    ("urls", {"count": {"min": None, "max": 0}}, "see https://example.com", "failed"),  # max 0 bans URLs
    ("code", {"count": {"min": 2, "max": 2}}, "```\nx\n```\n\n~~~\ny\n~~~", "passed"),
    ("code", {"count": {"min": 0, "max": 0}}, "use `x` and ``y``", "passed"),  # inline spans are not blocks
    ("code", {"count": {"min": None, "max": 0}}, "```\nx\n```", "failed"),  # max 0 disallows code
])
def test_a_bound_compares_what_the_check_counts(check: str, params: dict, text: str, status: str) -> None:
    result = run(check, params, text)
    assert result.status == status
    assert len(result.findings) == (1 if status == "failed" else 0)


# word lists: one matcher behind `contains`, `contains_any` and `contains_none`, three verdicts


@pytest.mark.parametrize(("check", "words", "params", "text", "findings"), [
    # verdicts: contains wants every word, contains_any one of them, contains_none none of them
    ("contains", ["Usage", "Examples"], {}, "Usage Examples", 0),
    ("contains_any", ["test", "tests", "pytest"], {}, "we run pytest", 0),
    ("contains_any", ["test", "tests", "pytest"], {}, "nothing here", 1),
    ("contains_none", ["TODO", "FIXME"], {}, "all clean", 0),
    ("contains_none", ["TODO", "FIXME"], {}, "a TODO and a fixme", 2),  # one finding per banned word found
    ("contains_none", ["TODO"], {}, "TODO TODO", 1),  # per word, not per occurrence
    # matching: whole words on \w boundaries, case-insensitive unless case_sensitive, phrases
    ("contains", ["Usage"], {}, "Usage: run it", 0),
    ("contains", ["Usage"], {}, "see usage below", 0),
    ("contains", ["Usage"], {}, "Usages vary", 1),
    ("contains", ["Usage"], {}, "reUsage", 1),
    ("contains", ["Usage"], {}, "", 1),
    ("contains", ["Usage"], {"case_sensitive": True}, "see usage below", 1),
    ("contains_none", ["TODO"], {"case_sensitive": True}, "a todo here", 0),
    ("contains", ["pytest -q"], {}, "run pytest -q now", 0),
    ("contains", ["pytest -q"], {}, "run -q pytest now", 1),
    # occurrences: bound each word on contains, the total across the list on contains_any
    ("contains", ["Usage"], {"occurrences": {"min": 4, "max": 4}}, "Usage usage USAGE Usage:", 0),
    ("contains_any", ["test", "tests", "pytest"], {"occurrences": {"min": 3, "max": 3}}, "test tests pytest", 0),
    ("contains_any", ["test", "tests", "pytest"], {"occurrences": {"min": 2, "max": None}}, "test only", 1),
])
def test_word_lists_match_whole_words_under_three_verdicts(
    check: str, words: list[str], params: dict, text: str, findings: int
) -> None:
    params = {"words": words, "case_sensitive": False, **params}
    if check != "contains_none":
        params.setdefault("occurrences", AT_LEAST_ONCE)
    result = run(check, params, text)
    assert result.status == ("failed" if findings else "passed")
    assert len(result.findings) == findings


# pattern lists: the same three verdicts against regexes, with the regex-only rules


@pytest.mark.parametrize(("check", "patterns", "params", "text", "findings"), [
    # verdicts, one row per check
    ("matches", ["^## [A-Z]"], {}, "intro\n## Usage\n", 0),  # MULTILINE: ^ applies per line
    ("matches", ["^## [A-Z]"], {}, "intro\n## usage\n", 1),  # no implicit case folding
    ("matches_any", ["pytest -q", "uv run"], {}, "uv run x", 0),
    ("matches_any", ["pytest -q", "uv run"], {}, "nothing", 1),
    ("matches_none", ["TODO", "FIXME"], {}, "all clean", 0),
    ("matches_none", ["TODO", "FIXME"], {}, "FIXME and TODO", 2),
    # users write (?i) to fold case
    ("matches", ["(?i)^## usage"], {}, "## Usage", 0),
    # occurrences: counted without overlap; the total across the list on matches_any
    ("matches", ["aa"], {"occurrences": {"min": 2, "max": 2}}, "aaaa", 0),
    ("matches", ["aa"], {"occurrences": {"min": 3, "max": 3}}, "aaaa", 1),  # not 3 overlapping
    ("matches", ["aa"], {"occurrences": {"min": None, "max": 1}}, "aaaa", 1),
    ("matches_any", ["pytest -q", "uv run"], {"occurrences": {"min": 2, "max": None}}, "pytest -q and uv run", 0),
    ("matches_any", ["pytest -q", "uv run"], {"occurrences": {"min": 2, "max": None}}, "pytest -q", 1),
])
def test_pattern_lists_match_regexes_under_three_verdicts(
    check: str, patterns: list[str], params: dict, text: str, findings: int
) -> None:
    params = {"patterns": patterns, **params}
    if check != "matches_none":
        params.setdefault("occurrences", AT_LEAST_ONCE)
    result = run(check, params, text)
    assert result.status == ("failed" if findings else "passed")
    assert len(result.findings) == findings


# allow/deny: one filter behind `urls` hosts and `code` languages; a finding per offending item, at its line


@pytest.mark.parametrize(("check", "params", "text", "lines"), [
    # deny + except is a whitelist, allow + except a blacklist
    ("urls", WHITELIST, "see https://docs.anthropic.com/x", ()),
    ("urls", WHITELIST, "see https://anthropic.com", (1,)),
    ("urls", WHITELIST, "see https://[your-host]/api", (1,)),  # a placeholder host is a finding, not a crash
    ("urls", BLACKLIST, "see http://localhost:8000/", (1,)),
    ("urls", BLACKLIST, "see https://example.com", ()),
    # hosts: a subdomain matches its parent, compared as host() gives it, not as a suffix or a path
    ("urls", WHITELIST, "see https://api.docs.anthropic.com/x", ()),
    ("urls", WHITELIST, "see https://user:pw@DOCS.Anthropic.COM:8443/x", ()),
    ("urls", WHITELIST, "see https://notdocs.anthropic.com/x", (1,)),
    ("urls", WHITELIST, "see https://example.com/docs.anthropic.com", (1,)),
    ("urls", WHITELIST, THREE_URLS, (1, 3)),
    # languages: the tag as written, matched literally but case-insensitively; not_specified is the untagged entry
    ("code", SHELL_ONLY, "```bash\nx\n```", ()),
    ("code", SHELL_ONLY, "```\nx\n```", ()),
    ("code", SHELL_ONLY, "```python\nx\n```", (1,)),
    ("code", SHELL_ONLY, "```sh\nx\n```", (1,)),
    ("code", {"default": "deny", "except": ["Bash"]}, "```BASH\nx\n```", ()),
    ("code", TAG_REQUIRED, "```bash\nx\n```", ()),
    ("code", TAG_REQUIRED, "```\nx\n```", (1,)),
    ("code", {"default": "deny", "except": ["bash"]}, THREE_BLOCKS, (3, 11)),  # at the opening fence
])
def test_a_policy_allows_or_denies_by_default_with_exceptions(
    check: str, params: dict, text: str, lines: tuple[int, ...]
) -> None:
    result = run(check, params, text)
    assert result.status == ("failed" if lines else "passed")
    assert [f.line for f in result.findings] == list(lines)


@pytest.mark.parametrize(("check", "params", "text"), [
    ("urls", {"count": {"min": None, "max": 1}, **WHITELIST}, "see https://bad.com and https://docs.anthropic.com"),
    ("code", {"count": {"min": None, "max": 1}, "default": "deny", "except": ["bash"]}, "```python\nx\n```\n\n```bash\ny\n```"),
])
def test_count_and_policy_findings_add_up(check: str, params: dict, text: str) -> None:
    result = run(check, params, text)
    assert result.status == "failed"
    assert len(result.findings) == 2


# paths: `style` and `except`, with `count` applied to what `except` leaves


@pytest.mark.parametrize(("params", "text", "status"), [
    ({}, "see src/main.py", "passed"),  # no parameters: only reports what it detected
    ({"style": "posix"}, "see src/main.py", "passed"),
    ({"style": "posix"}, "see src\\main.py", "failed"),
    ({"style": "windows"}, "see src\\main.py", "passed"),
    ({"style": "windows"}, "see src/main.py", "failed"),
    ({"style": "windows", "except": ["src/*"]}, "see src/a.py and C:\\x.py", "passed"),
    # except: the glob syntax of `exclude`, matched against the whole token
    ({"count": {"min": None, "max": 0}, "except": ["path/to/*"]}, "see path/to/file.py", "passed"),
    ({"count": {"min": None, "max": 0}, "except": ["path/to/*"]}, "see path/to/a/b.py", "failed"),
    ({"count": {"min": None, "max": 0}, "except": ["path/to/**"]}, "see path/to/a/b.py", "passed"),
    ({"count": {"min": None, "max": 0}, "except": ["<**>"]}, "see <path/to/file.py>", "passed"),
    ({"count": {"min": None, "max": 0}, "except": ["<**>"]}, "see path/to/file.py", "failed"),
    ({"count": {"min": None, "max": 0}, "except": ["path/to/*"]}, "see src/a.py and path/to/file.py", "failed"),
])
def test_paths_style_and_except_apply_to_the_detected_paths(params: dict, text: str, status: str) -> None:
    result = run("paths", params, text)
    assert result.status == status
    assert len(result.findings) == (1 if status == "failed" else 0)


# findings name the item; detected lists everything seen; severity decides the status


@pytest.mark.parametrize(("check", "params", "text", "named"), [
    ("contains", {"words": ["Usage", "Examples", "Notes"], "case_sensitive": False, "occurrences": AT_LEAST_ONCE}, "Usage only", ("Examples", "Notes")),
    ("contains", {"words": ["Usage", "Examples"], "case_sensitive": False, "occurrences": {"min": 1, "max": 3}}, "Usage Examples Examples Examples Examples", ("Examples",)),
    ("matches", {"patterns": ["^## [A-Z]", "TODO", "FIXME"], "occurrences": AT_LEAST_ONCE}, "## Usage", ("TODO", "FIXME")),
    ("urls", WHITELIST, THREE_URLS, ("https://bad.com", "https://worse.com")),
])
def test_one_finding_per_offending_item_names_it(check: str, params: dict, text: str, named: tuple[str, ...]) -> None:
    result = run(check, params, text)
    assert result.status == "failed"
    messages = [f.message for f in result.findings]
    assert len(messages) == len(named)
    for name in named:
        assert [m for m in messages if name in m], (name, messages)


@pytest.mark.parametrize(("check", "params", "text", "status", "detected"), [
    ("paths", {}, "see src/main.py", "passed", ("src/main.py",)),
    ("paths", {"except": ["path/to/*"]}, "see src/a.py and path/to/file.py", "passed", ("src/a.py", "path/to/file.py")),  # excepted stay
    ("urls", {}, "a https://a.com and http://b.com/x", "passed", ("https://a.com", "http://b.com/x")),
    ("urls", WHITELIST, "see https://bad.com and https://docs.anthropic.com", "failed", ("https://bad.com", "https://docs.anthropic.com")),  # failures included
    ("code", {}, "```bash\nx\n```\n\n```\ny\n```\n\n~~~Python\nz\n~~~", "passed", ("bash", "not_specified", "python")),
    ("code", {"default": "deny", "except": ["bash"]}, THREE_BLOCKS, "failed", ("python", "bash", "ruby")),
    ("words", {"min": None, "max": 1}, "see src/a.py and https://a.com", "failed", ()),
    ("contains", {"words": ["Usage"], "case_sensitive": False, "occurrences": AT_LEAST_ONCE}, "see src/a.py and https://a.com", "failed", ()),
    ("matches", {"patterns": ["^## [A-Z]"], "occurrences": AT_LEAST_ONCE}, "see src/a.py and https://a.com", "failed", ()),
])
def test_detected_lists_everything_a_heuristic_check_saw(
    check: str, params: dict, text: str, status: str, detected: tuple[str, ...]
) -> None:
    result = run(check, params, text)
    assert result.status == status
    assert result.detected == detected


@pytest.mark.parametrize(("check", "params", "severity", "text", "status", "detected"), [
    ("urls", {"count": {"min": None, "max": 0}}, "error", "see https://example.com", "failed", ("https://example.com",)),
    ("urls", {"count": {"min": None, "max": 0}}, "warn", "see https://example.com", "warned", ("https://example.com",)),
    ("urls", {"count": {"min": None, "max": 0}}, "warn", "no url", "passed", ()),
    ("chars", {}, "warn", "a\u00a0b", "warned", ()),  # a lint warns the same way
])
def test_severity_decides_the_status_of_findings(
    check: str, params: dict, severity: str, text: str, status: str, detected: tuple[str, ...]
) -> None:
    result = run(check, params, text, severity)
    assert result.status == status
    assert len(result.findings) == (0 if status == "passed" else 1)
    assert result.detected == detected


def test_contains_none_numbers_lines_as_splitlines_does() -> None:
    # \x0c is a line break for splitlines, as it is for every other check's line numbers
    result = run("contains_none", {"words": ["banned"], "case_sensitive": False}, "a\x0cb\nbanned here")
    assert [f.line for f in result.findings] == [3]
