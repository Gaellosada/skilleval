"""Declarative, file-based tests for LLM setups. `main` is the CLI over the same API."""

from importlib.metadata import version

from skilleval.cli import main

__version__ = version("skilleval")
__all__ = ["main", "__version__"]
