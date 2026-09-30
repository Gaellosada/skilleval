# Tests

- `unit/<package>/test_<module>.py` pins one module, through `load` where the module has no
  public entry of its own; `integration/<area>/` goes through `collect`, `run` or `main`.
- A test writes what it needs with the `project` fixture, inline. A `.eval.yml` used by an
  integration test lives in that test's folder, and only that module reads it.
- `integration/end_to_end/fixture/` is a realistic project frozen as it is: it pins one
  end-to-end run and never grows to cover a new behaviour. A new behaviour gets its own inline
  files, or its own small fixture in its own folder.
- No test starts a harness: `conftest` points `PATH` at an empty directory. A test of what runs
  one puts a program of its own there, under the harness's name. A test running a `run` command
  takes the `bash` fixture, which adds links to `bash` and the few tools the tests call, its
  `TOOLS`, never a folder of the system's.
