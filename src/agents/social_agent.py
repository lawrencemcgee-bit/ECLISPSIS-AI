"""
SocialAgent — local social-media post analysis via SocialContentService.
No posting/publishing: see that service's module docstring for why.
"""

from src.core.results import AgentResult


class SocialAgent:
    def __init__(self, service):
        self.service = service

    def analyze(self, text: str, platform: str = "generic"):
        data = self.service.analyze(text, platform)
        return AgentResult(agent="social", output=data)

    def execute(self, **kwargs):
        """Uniform entry point for AgentRegistry/AgentRouter dispatch."""
        return self.analyze(kwargs["text"], kwargs.get("platform", "generic"))
