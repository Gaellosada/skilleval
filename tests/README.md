# Tests

- `unit/<package>/test_<module>.py` calls one function; `integration/<area>/` goes through
  `collect`, `run` or `main`.
- A test writes what it needs with the `project` fixture, inline. A file too long to read
  inline lives in the test module's own folder, and only that module reads it.
- `integration/project/fixture/` is a realistic project frozen as it is: it pins one end-to-end
  run and never grows to cover a new behaviour. A new behaviour gets its own inline files, or
  its own small fixture in its own folder.
