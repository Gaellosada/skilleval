"""Declarative, file-based tests for LLM setups. `main` and `ExitCode` are the public API."""

from importlib.metadata import version

from skilleval.cli import ExitCode, main

__version__ = version("skilleval")
__all__ = ["ExitCode", "main", "__version__"]
