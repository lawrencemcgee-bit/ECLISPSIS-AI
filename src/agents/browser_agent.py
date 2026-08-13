"""
BrowserAgent — general-purpose fetch-and-read via BrowserService. See
that service's module docstring for what this is (and deliberately isn't
— no JS, no crawling, no interpretation of the fetched content).

Unlike Coding/Social/Creative, a fetch failure here is a real, expected
outcome (a URL is external, network-dependent input, unlike code or
text the caller already has in hand) — mirrors how AssistantCore.analyze()
already reports NCI fetch failures back in the result rather than
raising. Same pattern here: BrowserFetchError is caught and turned into
an AgentResult with metadata["error"] set, not left to propagate.
"""

from src.core.results import AgentResult
from src.services.browser_service import BrowserFetchError


class BrowserAgent:
    def __init__(self, service):
        self.service = service

    def fetch(self, url: str):
        try:
            data = self.service.fetch(url)
        except (ValueError, BrowserFetchError) as exc:
            return AgentResult(agent="browser", output=None, metadata={"error": str(exc)})
        return AgentResult(agent="browser", output=data)

    def execute(self, **kwargs):
        """Uniform entry point for AgentRegistry/AgentRouter dispatch."""
        return self.fetch(kwargs.get("url"))
