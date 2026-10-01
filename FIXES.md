# Bug-hunt fixes

Branch `fix-bug-hunt`, cut from local `main` at 5064974 (fetch refused: no SSH key in the session).
Per bug: reproduce, root cause, failing test, root fix, docs/specs, checks, one commit.
This file is deleted in the last commit.

| Bug | Status | Root cause → fix |
|-----|--------|------------------|
| B1 | done | `_URL` (`https?://\S+`) ran through `](`, merging a markdown link's text and target → stop a URL at a square bracket unless it wraps a host (`prompt.py:53`) |
| B2 | done | `_glob` stripped `./` from `include` but kept it on `exclude`, which is matched against paths relative to the include's base → strip `./` from each `exclude` glob there too (`testfile/__init__.py:149`) |
| B3 | done | `Path.glob` before 3.13 gives only directories for a trailing `**`, and only files count → glob a trailing `**` as `**/*`, the same files on every version (`runner.py:142`) |
| B4 | todo | |
| B5 | todo | |
| B6 | todo | |
| B7 | todo | |
| B8 | todo | |
| B9 | todo | |
| B10 | todo | |
