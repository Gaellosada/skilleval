"""Formats: the conventions of a named file format. Not specified yet, so each one passes."""

from typing import Any

from skilleval.static.prompt import Prompt
from skilleval.static.result import CheckFunction, Finding


def anthropic_skill(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


def anthropic_claude(prompt: Prompt, params: dict[str, Any]) -> list[Finding]:
    raise NotImplementedError


CHECKS: dict[str, CheckFunction] = {
    "anthropic-skill": anthropic_skill, "anthropic-claude": anthropic_claude,
}
