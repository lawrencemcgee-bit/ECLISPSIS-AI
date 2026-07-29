"""
LocalEngine implementation for Milestone 1.
Routes conversation requests through the local engine and returns typed results.
"""

from src.core.results import AssistantResult

class LocalEngine:
    def process(self, message: str) -> AssistantResult:
        """
        Milestone 1: simple deterministic response.
        Later milestones will replace this with agent routing, tools, tasks, etc.
        """
        return AssistantResult(
            content=f"LocalEngine received: {message}",
            metadata={"engine": "local", "milestone": 1}
        )


