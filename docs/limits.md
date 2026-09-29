# Limits

What skilleval does not support, and what it cannot keep out of a run, today. What is said of Claude Code was observed in a run of 2.1.284 or 2.1.285, unless it says it was read from the program, 2.1.285, or from its documentation.

## Platforms

skilleval is written for Linux, WSL included, which is what its suite and its CI run on. macOS is untested. Windows, outside WSL, is not supported:

- [`harness: blank`](evaluations.md#harness) takes every environment variable starting with `CLAUDE` out of the run, `CLAUDE_CODE_GIT_BASH_PATH` among them, which Claude Code reads on Windows to find Git Bash, as read from the program.
- The [settings file](config.md) and the configuration directory of `blank` are created for their user alone to read, modes `600` and `700`, which Windows ignores.
- skilleval's own suite does not run there: its stand-in for `claude` is a script.

On a filesystem that ignores case, the default on Windows and macOS, `.SkillEval` is `.skilleval` to the system and not to skilleval, which leaves only the exact name out of a [workspace](evaluations.md#workspace).

## `harness: blank`

`blank` leaves out the user's Claude Code configuration, their login and the environment variables starting with `ANTHROPIC_` or `CLAUDE`. What stays of the user and of the machine:

- The shell startup files. Claude Code builds the shell of its Bash tool from the startup file of the user's shell, `~/.bashrc` for bash and `~/.zshrc` for zsh, so the aliases, functions and shell options that file sets for a shell that is not interactive reach the model's commands. The variables it exports do not. Observed with bash; zsh and the shell options were read from the program.
- The rest of the home directory, such as the user's git identity: skilleval passes `HOME` as it is.
- The environment variables Claude Code reads under another name than `ANTHROPIC_` or `CLAUDE`, such as `MAX_THINKING_TOKENS`, as read from the program.
- The skills and agents Claude Code builds in.
- The settings an administrator manages: on the machine, as the documentation says, and for the account the token logs in.

## Credentials

- A model run with [`permissions: bypass`](evaluations.md#permissions) has the user's rights: it can read the credentials of its environment, and what it prints is kept in the [results](evaluations.md#results).
- A settings file written by hand keeps the mode it was given, and git ignores it from the first evaluation on.
- The workspaces and the configuration directories of `blank` are in the system's temporary directory, under folders every user of the machine can create first.

## Backends

[`backend: claude_api`](config.md#backend) is not supported yet: a test run with it is an error.
