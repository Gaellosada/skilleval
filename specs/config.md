# Settings

What belongs to whoever runs the tests, not to the tests: what runs the models, and the credentials it takes. A test file is shared and says what is tested; the settings are one user's and say what runs it on their machine.

```yaml
backend: claude_cli
CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...
```

## The file

`<base>/.skilleval/config.yml`, `<base>` being the project root, or the test file's directory in a file without `root`: beside the results an evaluation keeps ([evaluations.md](evaluations.md)), in the folder git ignores whole, so the file is never committed and can hold a credential.

An evaluation reads it as it starts, once its workspace is filled and before its first task, so a change applies to the next test. It writes `.skilleval/.gitignore` first, every time, so a file written by hand is ignored from the first evaluation on. A static check runs no model and reads no settings: it neither needs the file nor writes it.

When the file is missing, skilleval writes it, its user's alone to read, then reads it like any other. It holds the default `backend` and, as comments to fill in, the credentials:

```yaml
# The settings of skilleval for this project. They are yours alone: git ignores this folder.

# What runs the models: claude_cli, Claude Code run headless, or claude_api, the Claude API.
backend: claude_cli

# Credentials. One that is not written here is read from the environment variable of its name.
# ANTHROPIC_API_KEY: sk-ant-api03-...          # what the backend claude_api needs
# CLAUDE_CODE_OAUTH_TOKEN: sk-ant-oat01-...    # what the harness blank needs; `claude setup-token` prints one
```

A file that exists is never written again, whatever it holds.

## Keys

Every value is text that is not blank, read without the spaces around it. Any other key is an error, as is a key written twice. The file holds credentials, so an error shows nothing of what it holds, neither a value nor a key that is not one of the three: it names the key, or else the line when YAML gives one.

- `backend` — what runs the models, one of two. Required: the file always says what runs them, so a file without it is an error.
    - `claude_cli` — Claude Code run headless: the `claude` program on the `PATH`, as [evaluations.md](evaluations.md) describes.
    - `claude_api` — the Claude API, called with no program in between. It needs `ANTHROPIC_API_KEY`. Not supported yet: for now, a test run with it and a key is an error saying so.
- `ANTHROPIC_API_KEY` — a key of the Claude API. Optional.
- `CLAUDE_CODE_OAUTH_TOKEN` — a token of Claude Code, which `claude setup-token` prints. Optional. What the harness `blank` logs in with ([evaluations.md](evaluations.md)).

A credential the file does not write is read from the environment variable of its name, so a machine with no file to fill, such as a CI runner, sets the variable; a variable that is empty or blank holds none, and where both are set, the file wins. The credentials are for what skilleval starts with them and nothing else: the harness `user_local` logs in as its user set it up, with its environment as it is and nothing of the file, and nothing named `.skilleval` is copied into a workspace, from a `working_folder` or from a skill, neither of which can be such a folder or inside one ([evaluations.md](evaluations.md)). A credential is never required by itself: it unlocks what needs it, and only a test that needs one fails without it.

## Errors

Nothing falls back in silence: a test that cannot run with the settings as written is `ERROR`, as [evaluations.md](evaluations.md) reports any test that could not run properly, and never runs with another backend or credential instead. The reason names the file, and the key to write or change:

- a file that cannot be read or written, that is not valid YAML or not a mapping, as an empty one, or that holds an unknown key, a key twice, no `backend` or one other than the two, or a credential that is not text or is blank;
- `backend: claude_api` with no `ANTHROPIC_API_KEY`, in the file or the environment, the reason saying that the API cannot be used without a key;
- `backend: claude_api` with a key, not supported yet;
- `backend: claude_cli` with no `claude` program on the `PATH`, the reason naming the file as where `backend` is set;
- `harness: blank` under `backend: claude_cli` with no `CLAUDE_CODE_OAUTH_TOKEN`, in the file or the environment, the reason saying that the harness cannot log in without a token;
- `harness: blank` with a token that is refused, as one that expired, the reason being the harness's own, followed by the file the token is read from and how to get a new one.
