"""
CodingAgent — real local static analysis (structure, syntax, TODOs,
docstring coverage) and diffing via CodingService. Never executes code —
see CodingService's module docstring for why that's a hard rule here,
not just a scope choice.
"""

from src.core.results import AgentResult


class CodingAgent:
    def __init__(self, service):
        self.service = service

    def analyze(self, code: str, language: str = "python"):
        data = self.service.analyze(code, language)
        return AgentResult(agent="coding", output=data)

    def diff(self, old_code: str, new_code: str, old_label: str = "before", new_label: str = "after"):
        data = self.service.diff(old_code, new_code, old_label, new_label)
        return AgentResult(agent="coding", output=data)

    def execute(self, action: str = "analyze", **kwargs):
        """Uniform entry point for AgentRegistry/AgentRouter dispatch."""
        if action == "analyze":
            return self.analyze(kwargs["code"], kwargs.get("language", "python"))
        if action == "diff":
            return self.diff(
                kwargs["old_code"], kwargs["new_code"],
                kwargs.get("old_label", "before"), kwargs.get("new_label", "after"),
            )
        return AgentResult(agent="coding", output=None,
                            metadata={"error": f"unknown action '{action}'"})
