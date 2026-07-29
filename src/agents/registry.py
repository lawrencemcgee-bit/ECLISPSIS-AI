"""
Agent registry placeholder.
Maps agent names to callable handlers.
"""

class AgentRegistry:
    def __init__(self):
        self._agents = {}

    def register(self, name: str, handler):
        self._agents[name] = handler

    def get(self, name: str):
        return self._agents.get(name)

