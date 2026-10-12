# Limits

What skilleval does not support, and what it cannot keep out of a run, today. What is said of Claude Code was observed in a run of 2.1.284 or 2.1.285, unless it says it was read from the program, 2.1.285, or from its documentation. A statement naming another version was observed with that one, or read from its program.

## Platforms

skilleval is written for Linux, WSL included, which is what its suite and its CI run on. macOS is untested. Windows, outside WSL, is not supported:

- [`harness: blank`](evaluations.md#harness) takes every environment variable starting with `CLAUDE` out of the run, `CLAUDE_CODE_GIT_BASH_PATH` among them, which Claude Code reads on Windows to find Git Bash, as read from the program.
- The [settings file](config.md) is created for its user alone to read, mode `600`, which Windows ignores.
- The tests of the harness, in skilleval's own suite, do not run there: their stand-in for `claude` is a script.

On a filesystem that ignores case, the default on macOS, `.SkillEval` is `.skilleval` to the system and not to skilleval, which leaves only the exact name out of a [workspace](evaluations.md#workspace).

## `harness: blank`

`blank` leaves out the user's Claude Code configuration, their login and the environment variables starting with `ANTHROPIC_` or `CLAUDE`. What stays of the user and of the machine:

- The shell startup files. Claude Code builds the shell of its Bash tool from the startup file of the user's shell, `~/.bashrc` for bash and `~/.zshrc` for zsh, so the aliases, functions and shell options that file sets for a shell that is not interactive reach the model's commands. The variables it exports do not. Observed with bash; zsh and the shell options were read from the program.
- The rest of the home directory, such as the user's git identity: skilleval passes `HOME` as it is.
- The environment variables Claude Code reads under another name than `ANTHROPIC_` or `CLAUDE`, such as `MAX_THINKING_TOKENS`, as read from the program.
- The skills and agents Claude Code builds in.
- The settings an administrator manages: on the machine, as the documentation says, and for the account the token logs in.

## `override_system_prompt` and `append_system_prompt`

Both keys act on the instructions a user writes, their `CLAUDE.md`, and neither on Claude Code's own system prompt, which always stays: no key replaces it. Under `blank` the user's instructions are left out already, so the two keys do the same thing.

- Under `user_local`, the text reaches the model as the instructions of a project, "project instructions, checked into the codebase", and not as the user's, "user's private global instructions for all projects", which is how it reaches it under `blank`. Observed with 2.1.296.
- [`override_system_prompt`](evaluations.md#override_system_prompt) excludes the `CLAUDE.md` and the rules of the user's configuration directory, and nothing else. Observed with 2.1.296, for a `CLAUDE.md` that is a link too, named by the link's path.
- The instructions an administrator manages cannot be excluded, as read from the program, 2.1.296.
- The `CLAUDE.md` of the workspace is loaded under `blank`.
- Under `user_local`, the `CLAUDE.md` of the workspace stays under `override_system_prompt` too, and so does the user's auto-memory. Not observed.
- The patterns that exclude the user's instructions are the path of their configuration directory as written, and Claude Code reads them as globs. Under `user_local`, a path holding a character a glob does not read literally, one of `*`, `?`, `[`, `]`, `{`, `}`, `(`, `)`, `|`, `"` and `\`, therefore makes a test with `override_system_prompt` `ERROR`, naming the directory and the character, in place of a run with the user's instructions left in: use `harness: blank`, or a configuration directory whose path holds no such character. Observed with 2.1.296 for `(` alone: a configuration directory named `conf(1)` kept its rules, which the same directory named `conf1` lost. The other characters are refused for what a glob reads in them.
- The patterns are that path as written, and Claude Code matches them against absolute file paths: a `CLAUDE_CONFIG_DIR` that is relative or holds a `..` segment, and a configuration directory that is a link, the default `~/.claude` as one that `CLAUDE_CONFIG_DIR` names, are not refused, and may leave the user's instructions in place under `override_system_prompt`. Not observed.
- The text is read as a `CLAUDE.md`, not verbatim, and an `@path` in it is an import. Under `blank`, a relative one is resolved from the run's configuration directory, where skilleval writes the text, and not from the folder of the file that `file` names, so it is lost, while an absolute one is loaded: write the imports as absolute paths. Under `user_local`, no import is loaded, relative or absolute: the text has to hold what it needs. Under both, a block HTML comment of the text, `<!-- ... -->`, does not reach the model. Observed with 2.1.296.
- Under `user_local`, the variable that has Claude Code load the text, `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD`, also has it load the `CLAUDE.md` of any other directory the user's settings add. Not observed.
- Under `user_local`, the model can read and write the folder holding the text, as it can the workspace: Claude Code is given it as an added directory. Not observed.

## `judge`

A [`judge`](evaluations.md#judge) is run with no tool, no MCP server and none of the settings files of the user, the project or its folder. What still differs between two runs, or reaches it:

- A judge is a model: asked the same question twice on the same material, it can answer differently, and so can two models. Pin `model` and `effort` in [`judge_defaults`](evaluations.md#judge_defaults), and keep for a judge what a constraint or a `run` command cannot check.
- What it judges can hold text written for it, such as a reply saying "answer YES". Its system prompt tells it to follow nothing the sections hold; nothing enforces that.
- What Claude Code itself adds to a conversation reaches the judge: the platform, the date, the name of its model and the email address of the account logged in. It was given nothing of the user's `CLAUDE.md`, skills or servers, as a judge asked to list what its context held showed.
- Under `user_local`, the environment stays the user's, as for a setup: what Claude Code reads there, such as `MAX_THINKING_TOKENS` or `ANTHROPIC_BASE_URL`, applies to the judge, which so can differ between two users. `harness: blank` takes out the variables starting with `ANTHROPIC_` or `CLAUDE`.
- Under `user_local`, a login the user's settings files hold, such as an `apiKeyHelper`, is left out with those files, as the documentation of `--setting-sources` says; not observed. A user logged in that way gives the judge `harness: blank`.
- The settings an administrator manages apply, as under [`harness: blank`](#harness-blank), and they or the organization of the account can cap the judge's `effort`; a model that does not support effort, such as Claude Haiku 4.5, judges without one: see [`effort`](#effort).
- `max_tokens` is counted once the judge has answered, so a judge can go past it before the test reports `ERROR`.
- A `blank` judge with no token is found when the judge is asked: the tasks before it have run, and were billed, before the test reports `ERROR`.
- The reply and the files are given whole, whatever their length: one too long for the judge's limits, or for its model, is an `ERROR`.

## `effort`

- A maximum effort caps [`effort`](evaluations.md#effort): one in the user's settings, under `user_local`, one in the workspace's, one in the settings an administrator manages, and one the organization of the account sets for the model. Claude Code runs a task above it at the maximum, as read from the program.
- A hook of the user's settings, under `user_local`, of the workspace's or of those an administrator manages can give a request another effort, and a `CLAUDE_CODE_EFFORT_LEVEL` in the `env` of these settings replaces `effort`: Claude Code puts both above it, as read from the program.
- A model that does not support the level, such as `xhigh` or `max`, runs at a lower one, without a word, as read from the program.
- A model that does not support effort, such as Claude Haiku 4.5, runs without one, as the documentation says.

## `usage`

- [`max_seconds`](evaluations.md#max_seconds) counts Claude Code's start-up, before it asks the model anything, and the time its tools take to run: a slow machine or a slow test suite the model runs takes seconds from the task. So does, on the first task, what skilleval does to start Claude Code: copying the setup's [`skills`](evaluations.md#skills) into the workspace, writing its system prompt key as a `CLAUDE.md` and, under `blank`, emptying its configuration directory.
- [`max_output_tokens`](evaluations.md#max_output_tokens) may count Claude Code's own calls to a smaller model, such as the one that summarises a page for its WebFetch tool: Claude Code reports every model's output tokens together, without saying what they were for. Not observed.

## Credentials

- A model run with [`permissions: bypass`](evaluations.md#permissions) has the user's rights: it can read the credentials of its environment, and what it prints is kept in the [results](evaluations.md#results).
- A [`run`](evaluations.md#run) command has the user's rights and environment under any `permissions`, and so has the model's code it runs: see [`run`](#run).
- A settings file written by hand keeps the mode it was given, and git ignores it from the first evaluation on.
- The workspaces, the folders of the judges, the configuration directories of `blank` and the folders holding the instructions of `user_local` are in the system's temporary directory, under folders every user of the machine can create first.

## `run`

- A process that a [`run`](evaluations.md#run) command starts in a session of its own, with `setsid` or as a daemon, leaves the command's process group: it is not killed at the `timeout` nor once the command exits, and it can outlive the copy of the workspace.
- An absolute path into the workspace still points at the workspace from the copy, so a command writing through it changes what the model left: a symbolic link, and any path a tool wrote there, such as a `.venv` or a `pip install -e .` the model made in the workspace, through which Python run in the copy can write `__pycache__` into the workspace.
- A `run` command runs with the rights and the environment of the user running skilleval, whatever `permissions` and `harness: blank` withhold from the model, and so does the model's code it runs, such as a `conftest.py` the model wrote beside its tests: that code can read the files beside the test file, hidden tests included, and write where the next task of the chain reads, such as the workspace, one folder up from the copy.
- What the command prints is written to a temporary file with no limit on its size, only the last 64 KiB being read: a command printing in a loop until its `timeout` can fill the disk, or the memory where the temporary directory is held in it.

## Backends

[`backend: claude_api`](config.md#backend) is not supported yet: a test run with it is an error.
