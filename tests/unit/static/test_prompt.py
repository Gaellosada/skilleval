"""skilleval.static.prompt: reading a prompt and the extractors. Rules: specs/static-checking.md, Detection."""

import pytest
from conftest import Project

from skilleval.static.prompt import (
    Fence,
    Link,
    Prompt,
    PromptError,
    Token,
    fences,
    headings,
    host,
    links,
    paths,
    read,
    urls,
)

# read


@pytest.mark.parametrize("text", [
    "# Title\n\nbody\n",
    "---\nname: x\n---\n# Title\n",  # closed frontmatter stays in the text
    "# Title\n\n---\n\nbody\n",  # a rule after line 1 is not frontmatter
])
def test_read_returns_the_whole_text_with_its_path_and_root(project: Project, text: str):
    path = project.write("SKILL.md", text)
    assert read(path, project.root) == Prompt(text, path, project.root)


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


def test_read_keeps_a_leading_bom_in_the_text(project: Project):
    path = project.root / "SKILL.md"
    path.write_bytes(b"\xef\xbb\xbf# Title\n")
    assert read(path).text == "\ufeff# Title\n"


# extractors on an empty prompt


@pytest.mark.parametrize("extract", [fences, links, headings, paths, urls])
def test_empty_prompt_extracts_nothing(extract):
    assert extract(Prompt("")) == []


# fences: three or more backticks or tildes open a block, the same character at least as long closes it


@pytest.mark.parametrize(("text", "expected"), [
    # the tag is the first word after the fence, lowercased, not_specified when absent; the line is the opening fence
    ("intro\n```python\nprint(1)\nx = 2\n```\nafter\n", [Fence("python", 2)]),
    ("```\ncode\n```\n", [Fence("not_specified", 1)]),
    ("```Python\ncode\n```\n", [Fence("python", 1)]),
    ("```bash title=x\ncode\n```\n", [Fence("bash", 1)]),
    ("~~~SH\ncode\n~~~\n", [Fence("sh", 1)]),
    # closing: same character, at least as long; unclosed runs to the end
    ("```\na\n````\n```\nb\n```\n", [Fence("not_specified", 1), Fence("not_specified", 4)]),
    ("```\na\n~~~\n```\nb\n", [Fence("not_specified", 1)]),
    ("````md\n```py\nx\n```\n````\n```sh\ny\n```\n", [Fence("md", 1), Fence("sh", 6)]),
    ("# T\n```\na\n\nb\n", [Fence("not_specified", 2)]),
    # inline spans and indented code are not fences
    ("Use ```ls -la``` inline here.\n", []),
    ("    code\n    ```\n", []),
])
def test_fences_open_and_close_by_the_fence_rules(text: str, expected: list[Fence]):
    assert fences(Prompt(text)) == expected


# links: inline links and images outside fences, with their target as written


@pytest.mark.parametrize(("text", "expected"), [
    ("see [api](docs/api.md)\n\n![diagram](img/flow.png)\n", [Link("docs/api.md", 1), Link("img/flow.png", 3)]),
    ("[a](a.md) then [b](b.md) and ![c](c.png)\n", [Link("a.md", 1), Link("b.md", 1), Link("c.png", 1)]),
    ("```\n[a](x.md)\n```\n[b](y.md)\n", [Link("y.md", 4)]),
    ("[text][ref] and [other]\n\n[ref]: https://a.com\n[other]: x.md\n", []),  # reference-style, never
    ("[a](api.md#usage) [b](#usage)\n", [Link("api.md#usage", 1), Link("#usage", 1)]),
    ("[x](https://a.com/b)\n", [Link("https://a.com/b", 1)]),
    ('[a](./x.md "Title") [b](./y.md)\n', [Link("./x.md", 1), Link("./y.md", 1)]),  # a title never hides a target
])
def test_links_are_inline_links_and_images_outside_fences(text: str, expected: list[Link]):
    assert links(Prompt(text)) == expected


# headings: GitHub slugs of the ATX headings outside fences, duplicates numbered


@pytest.mark.parametrize(("text", "expected"), [
    ("# Usage\n", ["usage"]),
    ("## Getting Started\n", ["getting-started"]),
    ("### API: v2.0, ok!\n", ["api-v20-ok"]),
    ("# my_var-name\n", ["my_var-name"]),
    ("# The `read` function\n", ["the-read-function"]),
    ("# A\n## B\n### C\n#### D\n##### E\n###### F\n", ["a", "b", "c", "d", "e", "f"]),
    ("# Usage\n## Usage\n# Usage\n", ["usage", "usage-1", "usage-2"]),
    ("```bash\n# not a heading\n```\n# Yes\n", ["yes"]),
])
def test_headings_are_github_slugs_in_order(text: str, expected: list[str]):
    assert headings(Prompt(text)) == expected


# paths: a token with a separator, no ://, and a prefix, a trailing / or a dot in its last segment


@pytest.mark.parametrize(("text", "expected"), [
    ("see src/skilleval/cli.py here\n", [Token("src/skilleval/cli.py", 1)]),
    ("see ./tasks here\n", [Token("./tasks", 1)]),
    ("see ../x here\n", [Token("../x", 1)]),
    ("see /etc/hosts here\n", [Token("/etc/hosts", 1)]),
    ("see ~/.claude here\n", [Token("~/.claude", 1)]),
    ("see C:\\Users\\x here\n", [Token("C:\\Users\\x", 1)]),
    ("see docs/ here\n", [Token("docs/", 1)]),
    ("see docs\\readme.md here\n", [Token("docs\\readme.md", 1)]),
    ("see and/or here\n", []),
    ("see src/skilleval here\n", []),  # a bare directory reference is not a path
    ("see https://x.com/a.md here\n", []),
    ("see a.b here\n", []),
    # trailing .,:;) and wrapping backticks, quotes, parentheses and brackets are stripped; angle brackets stay
    ("see `src/cli.py`. here\n", [Token("src/cli.py", 1)]),
    ("see (docs/x.md) here\n", [Token("docs/x.md", 1)]),
    ("see [docs/x.md] here\n", [Token("docs/x.md", 1)]),
    ('see "docs/x.md" here\n', [Token("docs/x.md", 1)]),
    ("see 'docs/x.md' here\n", [Token("docs/x.md", 1)]),
    ("see <path/to/file.py> here\n", [Token("<path/to/file.py>", 1)]),
    ("see docs/x.md, here\n", [Token("docs/x.md", 1)]),
    ("see docs/x.md: here\n", [Token("docs/x.md", 1)]),
    ("see docs/x.md; here\n", [Token("docs/x.md", 1)]),
    ("see ./tasks) here\n", [Token("./tasks", 1)]),
    # inline spans count, fences do not, document order with lines
    ("Run `./tasks` and `src/cli.py` now\n", [Token("./tasks", 1), Token("src/cli.py", 1)]),
    ("```\npath/to/file.py\n```\nsee docs/x.md\n", [Token("docs/x.md", 4)]),
    ("x\n\nsee ./a.md and ./b.md\n\nthen /etc/hosts\n", [Token("./a.md", 3), Token("./b.md", 3), Token("/etc/hosts", 5)]),
])
def test_paths_are_path_looking_tokens_outside_fences_stripped_of_wrapping(text: str, expected: list[Token]):
    assert paths(Prompt(text)) == expected


# urls: https?:// and non-space characters anywhere, trailing punctuation stripped


@pytest.mark.parametrize(("text", "expected"), [
    ("see http://a.com/x\n\nand https://b.com/y\n", [Token("http://a.com/x", 1), Token("https://b.com/y", 3)]),
    ("https://a.com/1 https://a.com/2\n", [Token("https://a.com/1", 1), Token("https://a.com/2", 1)]),
    ("https://a.com/b?q=1&r=2#f\n", [Token("https://a.com/b?q=1&r=2#f", 1)]),
    ("```bash\ncurl https://api.example.com/v1\n```\n", [Token("https://api.example.com/v1", 2)]),  # fences included
    ("open `https://a.com/x` now\n", [Token("https://a.com/x", 1)]),
    ("ftp://a.com/x\n", []),
    ("see a.com/x and www.a.com\n", []),
] + [
    (f"see https://a.com/x{trailing} now\n", [Token("https://a.com/x", 1)])
    for trailing in [".", ",", ";", ":", "!", "?", ")", "]", '"', "`", ")."]
])
def test_urls_are_http_and_https_anywhere_stripped_of_trailing_punctuation(text: str, expected: list[Token]):
    assert urls(Prompt(text)) == expected


# host


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://Docs.Anthropic.COM:443/x", "docs.anthropic.com"),
        ("https://user:pass@Example.com:8443/p?q=1", "example.com"),
        ("http://127.0.0.1:8000/health", "127.0.0.1"),
        ("https://[your-host]/api", "[your-host]"),  # a bracketed placeholder is a host like any other, not a crash
    ],
)
def test_host_is_lowercased_without_port_credentials_or_path(url: str, expected: str):
    assert host(url) == expected
