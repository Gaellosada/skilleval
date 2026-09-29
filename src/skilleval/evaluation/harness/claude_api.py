"""The Claude API, called with no program in between: what the backend `claude_api` runs.
Not supported yet."""

from skilleval.evaluation.harness.base import HarnessError, Reply, Request


def ask(request: Request) -> Reply:
    """Raises `HarnessError`: for settings holding no key, and, the backend not being
    supported yet, for any other."""
    config = request.config
    if config.anthropic_api_key is None:
        raise HarnessError(f"no ANTHROPIC_API_KEY, and the backend claude_api cannot call the API without one: "
                           f"write it in {config.path}, or set backend to claude_cli there")
    raise HarnessError(f"the backend claude_api is not supported yet: set backend to claude_cli in {config.path}")
