"""
AgentRouter selects and runs agents based on message intent or explicit calls.
"""

from src.agents.registry import AgentRegistry
from src.core.event_bus import EventBus

class AgentRouter:
    def __init__(self, events: EventBus):
        self.registry = AgentRegistry()
        self.events = events

    def run(self, agent_name: str, *args, **kwargs):
        self.events.emit("agent.invoked", {"agent": agent_name})
        result = self.registry.run(agent_name, *args, **kwargs)
        self.events.emit("agent.completed", {"result": result})
        return result

