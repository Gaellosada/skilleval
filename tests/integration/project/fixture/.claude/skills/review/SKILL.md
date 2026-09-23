---
name: review
description: Describe what a refactoring changed and check that the suite still passes.
---

# Review

## Usage

Apply this skill after the refactor skill in ../refactor/SKILL.md has finished.
Compare the module before and after, name each refactoring from the catalogue in
../refactor/reference.md, and confirm that the tests still pass. Report the result
in three parts: what changed, why it is equivalent, and what remains to be done.
Keep the report shorter than the diff it describes, and never restate the code.

## Examples

Check the suite and the published model list in one go:

```Bash
pytest -x
curl -s https://api.anthropic.com/v1/models
```

A review reads like a short changelog entry:

```python
print("Extracted parse_header from parse; 12 tests pass.")
```
