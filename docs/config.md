# Settings

`.skilleval/config.yml` holds the settings of whoever runs the tests: what runs the models, and the credentials it takes. It sits under the project root, or under the test file's directory in a file without [`root`](test-file.md#root), beside the [results](evaluations.md#results). Git ignores `.skilleval/`, so the file is never committed.

```yaml
backend: claude_cli
CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...
```

An evaluation reads the file as it starts. When the file is missing, it writes it first, with `backend: claude_cli` and the credentials as comments to fill in; a file that exists is never written again. A static check neither reads nor writes it.

Any other key than the three below is an error, as is a key written twice.

## `backend`

Required. What runs the models.

- `claude_cli`, the default of the file skilleval writes: Claude Code run headless, the `claude` program on the `PATH`, as [`harness`](evaluations.md#harness) describes.
- `claude_api`: the Claude API, called with no program in between. It needs [`ANTHROPIC_API_KEY`](#anthropic_api_key). Not supported yet: a test run with it is an error.

## `ANTHROPIC_API_KEY`

Optional. A key of the Claude API, text that is not blank: `ANTHROPIC_API_KEY: sk-ant-api03-...`. Needed by `backend: claude_api`.

## `CLAUDE_CODE_OAUTH_TOKEN`

Optional. A token of Claude Code, text that is not blank, which `claude setup-token` prints: `CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...`. Nothing needs it yet.

## Environment

A credential the file does not write is read from the environment variable of its name. Where both are set, the file wins.

## Errors

Nothing falls back in silence: a test that cannot run with the settings as written is `ERROR`, and its reason names the file.

| Settings | Reason |
|---|---|
| The file cannot be read or written, is not a mapping, as an empty one, or holds an unknown key, no `backend`, a `backend` other than the two, or a credential that is blank or not text | what to fix, at its key |
| `backend: claude_api`, no `ANTHROPIC_API_KEY` in the file or the environment | the API cannot be called without a key |
| `backend: claude_api`, with a key | `claude_api` is not supported yet |
| `backend: claude_cli`, no `claude` program on the `PATH` | install Claude Code; the file is where `backend` is set |
