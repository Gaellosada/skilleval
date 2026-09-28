# Command line

`skilleval [paths ...] [-k WORD] [-x] [-q | -v] [--static-checks | --evaluations] [--collect-only] [--version] [-h]`

Collects the cases named by the arguments, runs them and prints a report, in pytest's shape.

## Arguments

Files, directories or node ids; the current directory when there are none. A path that does not exist, a malformed node id, a node id on a directory, or one that addresses nothing, is a usage error.

## Discovery

A directory collects every `*.eval.yml` and `*.eval.yaml` below it, recursively and in sorted order, skipping dot-directories, `node_modules`, `venv` and `site-packages` below it, but not dot-files. A file or directory named explicitly is taken whatever its name. A case named twice is collected once.

Every collected file must be a valid [test file](test-file.md); one that is not is a load error naming it.

## Node ids

A node id addresses cases: the file, `::`, the test id, then the case's file in brackets when it has one. Paths are posix and relative to the current directory.

- An evaluation, a test with an inline prompt, or an `include` that matched nothing, has one case addressed by `file::id` alone; brackets are a usage error.
- A test whose prompt is a `file` has one case, addressed by `file::id` or `file::id[path]`.
- A test with an `include` has one case per matched file. `file::id` selects all of them; `file::id[path]` selects one.

## Options

### `-k`

`-k WORD` keeps only the cases whose node id contains `WORD`: a plain, case-sensitive substring.

### `-x`

`-x`, or `--exitfirst`, stops at the first failure or error.

### `-q`

`-q`, or `--quiet`, prints only the failures, the errors and the summary. `-q` and `-v` together are a usage error.

### `-v`

`-v`, or `--verbose`, prints one line per case, with its findings and what each heuristic check detected.

### `--static-checks`

Keeps only the cases of the `static-check` tests, among those the arguments and `-k` select: `skilleval --static-checks evals/` checks every prompt and starts no harness, so it costs nothing. A kept test that [`needs`](test-file.md#needs) an evaluation is `SKIPPED`, as `needs <id>, not selected`, and a test that needs that one in turn as `needs <that test>`. `--static-checks` and `--evaluations` together are a usage error.

### `--evaluations`

Keeps only the cases of the `evaluation` tests, in the same way: `skilleval --evaluations evals/`. An evaluation that `needs` a static check is `SKIPPED`, since the check did not run; to run it, leave the flag out or take the `needs` away.

### `--collect-only`

Prints the node ids of the collected cases and runs nothing.

### `--version`

Prints the version.

### `-h`

`-h`, or `--help`, prints the usage and every option.

## Output

The report opens with `collected N cases`, except with `-q`; nothing collected prints `no cases collected` alone. Each case ends `PASSED`, `FAILED`, `SKIPPED` or `ERROR`. By default the report prints one progress character per case, grouped by file: `.` passed, `F` failed, `E` error, `s` skipped.

- A `FAILED` case lists its findings as `check: message`, with `(line N)` when the finding has a line and `[warn]` after a warning.
- With `-v`, a `SKIPPED` case says why, such as the test it `needs`.
- An `ERROR` case could not run: it gives the reason and how many checks were skipped.
- An evaluation names what each finding is about before the check, as `response: words: ...`, and its workspace last, as `workspace: <path>`: under a failure or an error, and with `-v` under every evaluation that ran. See [evaluations.md](evaluations.md#report).

`FAILED` cases then list under a `FAILURES` heading, `ERROR` cases under `ERRORS`. By default and with `-q`, only `FAILED` cases list their findings; with `-v`, every case does, warnings of a passing case included.

The summary line counts the cases by status, and one warning per warned check per case, in the order failed, passed, skipped, error, warning, leaving out a count of 0, then gives the time.

## Exit codes

| Code | `ExitCode` | Meaning |
|---|---|---|
| 0 | `OK` | no case failed or errored |
| 1 | `TESTS_FAILED` | a case failed or errored |
| 2 | `LOAD_ERROR` | a collected file is not a valid test file |
| 3 | `INTERNAL_ERROR` | an unexpected error in skilleval |
| 4 | `USAGE_ERROR` | an unknown flag, `-q` with `-v`, `--static-checks` with `--evaluations`, or a bad path or node id (see [Arguments](#arguments)) |
| 5 | `NO_TESTS_COLLECTED` | nothing was collected |

Warnings never affect the exit code. A load or usage error prints to standard error.

## Python API

`main` and `ExitCode`, imported from `skilleval`, are the whole public API. `main(argv)` runs the command line with the argument list `argv` (`sys.argv[1:]` when omitted) and returns an `ExitCode`, an `IntEnum` of the codes above.
