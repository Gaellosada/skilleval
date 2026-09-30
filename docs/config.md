# Settings

`.skilleval/config.yml` holds the settings of whoever runs the tests: what runs the models, and the credentials it takes. It sits under the project root, or under the test file's directory in a file without [`root`](test-file.md#root), beside the [results](evaluations.md#results). Git ignores `.skilleval/`, so the file is never committed.

```yaml
backend: claude_cli
CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...
```

An evaluation reads the file as it starts, and writes `.skilleval/.gitignore` before it does, every time. When the file is missing, it writes it first, readable by its user alone, with `backend: claude_cli` and the credentials as comments to fill in; a file that exists is never written again. A static check neither reads nor writes it, nor the `.gitignore`: a file written by hand is ignored from the first evaluation on.

Every value is text that is not blank, read without the spaces around it. Any other key than the three below is an error, as is a key written twice. An error shows nothing of what the file holds: it names the key, or else the line when YAML gives one.

## `backend`

Required. What runs the models.

- `claude_cli`, the default of the file skilleval writes: Claude Code run headless, the `claude` program on the `PATH`, as [`harness`](evaluations.md#harness) describes.
- `claude_api`: the Claude API, called with no program in between. It needs [`ANTHROPIC_API_KEY`](#anthropic_api_key). Not supported yet: a test run with it is an error.

## `ANTHROPIC_API_KEY`

Optional. A key of the Claude API, text that is not blank: `ANTHROPIC_API_KEY: sk-ant-api03-...`. Needed by `backend: claude_api`.

## `CLAUDE_CODE_OAUTH_TOKEN`

Optional. A token of Claude Code, text that is not blank, which `claude setup-token` prints: `CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...`. Needed by [`harness: blank`](evaluations.md#harness), which logs in with it.

## Environment

A credential the file does not write is read from the environment variable of its name; a variable that is empty or blank holds none. Where both are set, the file wins.

The harness `user_local` logs in as its user set it up: it runs with its environment as it is, and with nothing of the file. A [`working_folder`](evaluations.md#working_folder) and a [skill](evaluations.md#skills) are copied into the workspace without anything named `.skilleval`, and neither can name such a folder or one inside it.

What can reach a credential is listed in [limits.md](limits.md#credentials).

## Errors

Nothing falls back in silence: a test that cannot run with the settings as written is `ERROR`, and its reason names the file.

| Settings | Reason |
|---|---|
| The file cannot be read or written, is not valid YAML or not a mapping, as an empty one, or holds an unknown key, a key twice, no `backend`, a `backend` other than the two, or a credential that is blank or not text | what to fix, at its key or its line |
| `backend: claude_api`, no `ANTHROPIC_API_KEY` in the file or the environment | the API cannot be called without a key |
| `backend: claude_api`, with a key | `claude_api` is not supported yet |
| `backend: claude_cli`, no `claude` program on the `PATH` | install Claude Code; the file is where `backend` is set |
| `backend: claude_cli` and `harness: blank`, no `CLAUDE_CODE_OAUTH_TOKEN` in the file or the environment | the harness cannot log in without a token |
| `harness: blank`, a token that is refused, as one that expired | what the harness says, then the file the token is read from; `claude setup-token` prints a new one |
