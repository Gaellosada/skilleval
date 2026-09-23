---
name: refactor
description: Restructure Python code in small steps that keep the suite green.
---

# Refactor

## Usage

Apply this skill when the user asks to restructure existing Python code without
changing what it does. Read the module first, then make one change at a time and
run the tests after each step, so every step stays small enough to revert alone.
The catalogue of refactorings lives in ./reference.md next to this file, and the
review skill in ../review/SKILL.md says how to describe the result. The conventions
for skill files are described at https://docs.anthropic.com/skills.

## Examples

Extract a function from a long method, rename a variable across a module, or
replace a chain of conditionals with a lookup table. After each change, run the
whole test suite from the project root:

```bash
pytest -q
```

A placeholder stands for the module under work and is never a real path:

~~~
path/to/module.py
~~~

## Stopping

Stop as soon as pytest reports a failure and say which refactoring broke it.
