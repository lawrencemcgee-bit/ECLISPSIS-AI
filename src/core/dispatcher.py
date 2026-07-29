"""
Unified event dispatcher for routing events between engine, agents, voice,
vision, UI, and tasks. Milestone 1: synchronous callbacks only.
"""

from typing import Callable, Dict, List
from .events import Event

class EventDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def register(self, event_type: str, callback: Callable):
        """Register a callback for a specific event type."""
        self._listeners.setdefault(event_type, []).append(callback)

    def dispatch(self, event: Event):
        """Dispatch an event to all registered listeners."""
        for callback in self._listeners.get(event.type, []):
            callback(event)

