"""Formats: the conventions of a named file format. Not specified yet, so each one passes."""

from __future__ import annotations


def anthropic_skill(prompt, params):
    raise NotImplementedError


def anthropic_claude(prompt, params):
    raise NotImplementedError


CHECKS = {"anthropic-skill": anthropic_skill, "anthropic-claude": anthropic_claude}
