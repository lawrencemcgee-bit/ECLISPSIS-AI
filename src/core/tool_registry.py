"""
ToolRegistry maps tool names to callable tool adapters.
Milestone 6: used by agents and tasks.
"""

from typing import Callable, Dict, Optional

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, handler: Callable):
        self._tools[name] = handler

    def get(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def run(self, name: str, *args, **kwargs):
        tool = self.get(name)
        if tool is None:
            return {"error": f"tool_not_found: {name}"}
        return tool(*args, **kwargs)


