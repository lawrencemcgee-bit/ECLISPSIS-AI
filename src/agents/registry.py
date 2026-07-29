"""
Agent registry for Milestone 1.
Maps agent names to callable handlers and ensures typed AgentResult output.
"""

from src.core.results import AgentResult

class AgentRegistry:
    def __init__(self):
        self._agents = {}

    def register(self, name: str, handler):
        self._agents[name] = handler

    def get(self, name: str):
        return self._agents.get(name)

    def run(self, name: str, *args, **kwargs) -> AgentResult:
        handler = self.get(name)
        if handler is None:
            return AgentResult(agent=name, output=None, metadata={"error": "agent_not_found"})
        output = handler(*args, **kwargs)
        return AgentResult(agent=name, output=output)


