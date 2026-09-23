"""`skilleval` on the command line. Specified in specs/cli.md."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Parse `argv` (`sys.argv[1:]` when None), collect, run, print, and return pytest's exit
    code: 0 passed, 1 failures or errors, 2 load error, 3 internal error, 4 usage error, 5
    nothing collected."""
    raise NotImplementedError
