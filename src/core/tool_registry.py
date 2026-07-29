"""
ToolRegistry will later map tool names to callable tool adapters.
Milestone 2: structure only.
"""

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name: str, handler):
        self._tools[name] = handler

    def get(self, name: str):
        return self._tools.get(name)

