"""skilleval.static.prompt: reading a prompt and the extractors. Rules: specs/static-checking.md, Detection."""

from __future__ import annotations

import pytest
from conftest import Project

from skilleval.static.prompt import Fence, Link, Prompt, PromptError, Token, fences, headings, host, links, paths, read, urls

# read


def test_read_returns_the_exact_text_with_path_and_no_root(project: Project):
    path = project.write("SKILL.md", "# Title\n\nbody\n")
    assert read(path) == Prompt("# Title\n\nbody\n", path, None)


def test_read_keeps_the_root_it_is_given(project: Project):
    path = project.write("SKILL.md", "x\n")
    assert read(path, project.root) == Prompt("x\n", path, project.root)


def test_read_missing_file_is_a_prompt_error(project: Project):
    path = project.root / "missing.md"
    with pytest.raises(PromptError) as e:
        read(path)
    assert path.name in str(e.value)


def test_read_undecodable_bytes_is_a_prompt_error(project: Project):
    path = project.root / "SKILL.md"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(PromptError) as e:
        read(path)
    assert path.name in str(e.value)


def test_read_unclosed_frontmatter_is_a_prompt_error(project: Project):
    path = project.write("SKILL.md", "---\nname: x\ndescription: y\n")
    with pytest.raises(PromptError) as e:
        read(path)
    assert path.name in str(e.value)


def test_read_closed_frontmatter_returns_the_whole_file(project: Project):
    text = "---\nname: x\n---\n# Title\n"
    assert read(project.write("SKILL.md", text)).text == text


def test_read_a_rule_after_line_one_is_not_frontmatter(project: Project):
    text = "# Title\n\n---\n\nbody\n"
    assert read(project.write("SKILL.md", text)).text == text


def test_read_keeps_a_leading_bom_in_the_text(project: Project):
    path = project.root / "SKILL.md"
    path.write_bytes(b"\xef\xbb\xbf# Title\n")
    assert read(path).text == "\ufeff# Title\n"


# empty prompt


@pytest.mark.parametrize("extract", [fences, links, headings, paths, urls])
def test_empty_prompt_extracts_nothing(extract):
    assert extract(Prompt("")) == []


# fences


def test_backtick_fence_gives_lang_line_and_body():
    [fence] = fences(Prompt("intro\n```python\nprint(1)\nx = 2\n```\nafter\n"))
    assert (fence.lang, fence.line) == ("python", 2)
    assert fence.body.splitlines() == ["print(1)", "x = 2"]


@pytest.mark.parametrize(
    ("opening", "lang"),
    [("```", "not_specified"), ("```Python", "python"), ("```bash title=x", "bash"), ("~~~SH", "sh")],
)
def test_lang_is_the_first_word_after_the_fence_lowercased(opening: str, lang: str):
    closing = opening[:3]
    assert [f.lang for f in fences(Prompt(f"{opening}\ncode\n{closing}\n"))] == [lang]


def test_a_longer_closing_fence_closes():
    [fence] = fences(Prompt("```\na\n````\nb\n"))
    assert fence.body.splitlines() == ["a"]


@pytest.mark.parametrize(("opening", "other"), [("```", "~~~"), ("~~~", "```")])
def test_a_fence_is_not_closed_by_the_other_character(opening: str, other: str):
    [fence] = fences(Prompt(f"{opening}\na\n{other}\nb\n"))
    assert fence.body.splitlines() == ["a", other, "b"]


def test_an_unclosed_fence_runs_to_the_end_of_file():
    [fence] = fences(Prompt("# T\n```\na\n\nb\n"))
    assert fence.line == 2
    assert fence.body.splitlines() == ["a", "", "b"]


def test_a_shorter_fence_inside_a_longer_one_stays_inside():
    [fence] = fences(Prompt("````md\n```py\nx\n```\n````\n"))
    assert fence.lang == "md"
    assert fence.body.splitlines() == ["```py", "x", "```"]


def test_two_fences_are_two_blocks_with_their_own_bodies():
    text = "```py\na\n```\n```sh\nb\n```\n"
    assert [(f.lang, f.line, f.body.splitlines()) for f in fences(Prompt(text))] == [("py", 1, ["a"]), ("sh", 4, ["b"])]


@pytest.mark.parametrize("text", ["Run `ls` now\n", "Use ```ls -la``` inline here.\n", "    code\n    ```\n"])
def test_inline_spans_and_indented_code_are_not_fences(text: str):
    assert fences(Prompt(text)) == []


# links


def test_links_and_images_give_the_target_and_line():
    text = "see [api](docs/api.md)\n\n![diagram](img/flow.png)\n"
    assert links(Prompt(text)) == [Link("docs/api.md", 1), Link("img/flow.png", 3)]


def test_several_links_on_one_line_are_all_returned_in_order():
    text = "[a](a.md) then [b](b.md) and ![c](c.png)\n"
    assert links(Prompt(text)) == [Link("a.md", 1), Link("b.md", 1), Link("c.png", 1)]


def test_links_inside_fences_are_skipped():
    text = "```\n[a](x.md)\n```\n[b](y.md)\n"
    assert links(Prompt(text)) == [Link("y.md", 4)]


def test_reference_style_links_are_not_returned():
    assert links(Prompt("[text][ref] and [other]\n\n[ref]: https://a.com\n[other]: x.md\n")) == []


def test_link_targets_keep_their_anchor():
    text = "[a](api.md#usage) [b](#usage)\n"
    assert links(Prompt(text)) == [Link("api.md#usage", 1), Link("#usage", 1)]


def test_a_link_with_a_url_target_is_returned():
    assert links(Prompt("[x](https://a.com/b)\n")) == [Link("https://a.com/b", 1)]


# headings


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("# Usage", "usage"),
        ("## Getting Started", "getting-started"),
        ("### API: v2.0, ok!", "api-v20-ok"),
        ("# my_var-name", "my_var-name"),
        ("# The `read` function", "the-read-function"),
    ],
)
def test_heading_slugs_follow_github(heading: str, slug: str):
    assert headings(Prompt(f"{heading}\n")) == [slug]


def test_every_atx_level_is_a_heading_in_order():
    text = "# A\n## B\n### C\n#### D\n##### E\n###### F\n"
    assert headings(Prompt(text)) == ["a", "b", "c", "d", "e", "f"]


def test_duplicate_headings_are_numbered():
    assert headings(Prompt("# Usage\n## Usage\n# Usage\n")) == ["usage", "usage-1", "usage-2"]


def test_headings_inside_fences_are_skipped():
    assert headings(Prompt("```bash\n# not a heading\n```\n# Yes\n")) == ["yes"]


# paths


@pytest.mark.parametrize(
    "token",
    ["src/skilleval/cli.py", "./tasks", "../x", "/etc/hosts", "~/.claude", r"C:\Users\x", "docs/", "path/to/file.py", r"docs\readme.md"],
)
def test_path_looking_tokens_are_detected(token: str):
    assert paths(Prompt(f"see {token} here\n")) == [Token(token, 1)]


@pytest.mark.parametrize("token", ["and/or", "src/skilleval", "https://x.com/a.md", "a.b"])
def test_tokens_that_are_not_paths_are_not_detected(token: str):
    assert paths(Prompt(f"see {token} here\n")) == []


@pytest.mark.parametrize(
    ("token", "path"),
    [
        ("`src/cli.py`.", "src/cli.py"),
        ("(docs/x.md)", "docs/x.md"),
        ("[docs/x.md]", "docs/x.md"),
        ('"docs/x.md"', "docs/x.md"),
        ("'docs/x.md'", "docs/x.md"),
        ("<path/to/file.py>", "<path/to/file.py>"),
        ("docs/x.md,", "docs/x.md"),
        ("docs/x.md:", "docs/x.md"),
        ("docs/x.md;", "docs/x.md"),
        ("./tasks)", "./tasks"),
    ],
)
def test_paths_are_stripped_of_trailing_punctuation_and_wrapping(token: str, path: str):
    assert paths(Prompt(f"see {token} here\n")) == [Token(path, 1)]


def test_paths_in_inline_code_spans_count():
    assert paths(Prompt("Run `./tasks` and `src/cli.py` now\n")) == [Token("./tasks", 1), Token("src/cli.py", 1)]


def test_paths_in_fences_are_skipped_and_detection_resumes_after():
    text = "```\npath/to/file.py\n```\nsee docs/x.md\n"
    assert paths(Prompt(text)) == [Token("docs/x.md", 4)]


def test_paths_are_returned_in_document_order_with_lines():
    text = "x\n\nsee ./a.md and ./b.md\n\nthen /etc/hosts\n"
    assert paths(Prompt(text)) == [Token("./a.md", 3), Token("./b.md", 3), Token("/etc/hosts", 5)]


# urls


def test_http_and_https_urls_are_detected_with_their_line():
    text = "see http://a.com/x\n\nand https://b.com/y\n"
    assert urls(Prompt(text)) == [Token("http://a.com/x", 1), Token("https://b.com/y", 3)]


@pytest.mark.parametrize("trailing", [".", ",", ";", ":", "!", "?", ")", "]", '"', "`", ")."])
def test_trailing_punctuation_is_stripped_from_urls(trailing: str):
    assert urls(Prompt(f"see https://a.com/x{trailing} now\n")) == [Token("https://a.com/x", 1)]


def test_a_url_keeps_its_query_and_fragment():
    assert urls(Prompt("https://a.com/b?q=1&r=2#f\n")) == [Token("https://a.com/b?q=1&r=2#f", 1)]


def test_urls_inside_fences_are_detected():
    text = "```bash\ncurl https://api.example.com/v1\n```\n"
    assert urls(Prompt(text)) == [Token("https://api.example.com/v1", 2)]


def test_urls_inside_inline_code_spans_are_detected():
    assert urls(Prompt("open `https://a.com/x` now\n")) == [Token("https://a.com/x", 1)]


def test_several_urls_on_one_line_are_returned_in_order():
    text = "https://a.com/1 https://a.com/2\n"
    assert urls(Prompt(text)) == [Token("https://a.com/1", 1), Token("https://a.com/2", 1)]


@pytest.mark.parametrize("text", ["ftp://a.com/x\n", "see a.com/x and www.a.com\n"])
def test_other_schemes_and_bare_domains_are_not_urls(text: str):
    assert urls(Prompt(text)) == []


# host


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://Docs.Anthropic.COM:443/x", "docs.anthropic.com"),
        ("https://user:pass@Example.com:8443/p?q=1", "example.com"),
        ("http://127.0.0.1:8000/health", "127.0.0.1"),
    ],
)
def test_host_is_lowercased_without_port_credentials_or_path(url: str, expected: str):
    assert host(url) == expected
