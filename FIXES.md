# Bug-hunt fixes

Branch `fix-bug-hunt`, cut from local `main` at 5064974 (fetch refused: no SSH key in the session).
Per bug: reproduce, root cause, failing test, root fix, docs/specs, checks, one commit.
This file is deleted in the last commit.

| Bug | Status | Root cause → fix |
|-----|--------|------------------|
| B1 | done | `_URL` (`https?://\S+`) ran through `](`, merging a markdown link's text and target → stop a URL at a square bracket unless it wraps a host (`prompt.py:53`) |
| B2 | done | `_glob` stripped `./` from `include` but kept it on `exclude`, which is matched against paths relative to the include's base → strip `./` from each `exclude` glob there too (`testfile/__init__.py:149`) |
| B3 | done | `Path.glob` before 3.13 gives only directories for a trailing `**`, and only files count → glob a trailing `**` as `**/*`, the same files on every version (`runner.py:142`) |
| B4 | done | `shutil.rmtree` in `keep` and `fill` stops at an entry the model left read-only → `_delete` moves the tree into a `TemporaryDirectory` beside it, whose cleanup deletes read-only trees, as the copies of `run` blocks are deleted (`workspace.py:56`) |
| B5 | partly done | The reason was `stderr + stdout` whole → reason is stderr plus the bounded `tail` a `run` failure ends with, moved to `harness/base.py` so `claude_code` reaches it without an import cycle (`claude_code.py:141`). STOPPED on keeping the streamed lines of a crashed task: the spec keeps "every task that returned", so it is a spec change and needs a transcript on `HarnessError` through `evaluation.run` and `judge.ask` — reported as a choice. |
| B6 | done | `_reply` parsed only the last line printed → read the lines from the end, split on `\n` alone, and take the first of type `result` (`claude_code.py:126`) |
| B7 | todo | |
| B8 | todo | |
| B9 | todo | |
| B10 | todo | |
