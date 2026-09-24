"""Formats: the conventions of a named file format. Not specified yet, so each one passes."""

from typing import Any

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def _unspecified(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    return []


CHECKS: dict[str, CheckFunction] = dict.fromkeys(("anthropic-skill", "anthropic-claude"), _unspecified)
