"""
Unified event dispatcher placeholder.
Milestone 1: no real routing yet — only structure.
"""

class EventDispatcher:
    def __init__(self):
        self._listeners = {}

    def register(self, event_type: str, callback):
        self._listeners.setdefault(event_type, []).append(callback)

    def dispatch(self, event):
        for callback in self._listeners.get(event.type, []):
            callback(event)

