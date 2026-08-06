"""
Agent registry.
Maps agent names to agent objects; dispatches via each agent's uniform
execute() method (added in Phase 3) and returns typed AgentResult output.
"""

from src.core.results import AgentResult

class AgentRegistry:
    def __init__(self):
        self._agents = {}

    def register(self, name: str, handler):
        self._agents[name] = handler

    def get(self, name: str):
        return self._agents.get(name)

    def run(self, name: str, **kwargs) -> AgentResult:
        handler = self.get(name)
        if handler is None:
            return AgentResult(agent=name, output=None, metadata={"error": "agent_not_found"})
        try:
            return handler.execute(**kwargs)
        except Exception as exc:
            # Graceful degradation (Engineering Charter §5): an agent
            # failure should produce a typed error result, not crash the
            # caller or leave the failure unreported.
            return AgentResult(agent=name, output=None, metadata={"error": str(exc)})


