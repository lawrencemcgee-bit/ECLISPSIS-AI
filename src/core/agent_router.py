"""
AgentRouter selects and runs agents based on message intent or explicit calls.
"""

from src.agents.registry import AgentRegistry
from src.core.event_bus import EventBus

class AgentRouter:
    def __init__(self, events: EventBus):
        self.registry = AgentRegistry()
        self.events = events

    def run(self, agent_name: str, **kwargs):
        self.events.emit("agent.invoked", {"agent": agent_name})
        result = self.registry.run(agent_name, **kwargs)
        if result.metadata and result.metadata.get("error"):
            self.events.emit("agent.failed", {"agent": agent_name, "error": result.metadata["error"]})
        else:
            self.events.emit("agent.completed", {"result": result})
        return result
