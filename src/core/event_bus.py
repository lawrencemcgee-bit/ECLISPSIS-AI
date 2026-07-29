"""
EventBus provides a unified, typed event gateway for the assistant.
"""

class EventBus:
    def __init__(self):
        self.listeners = {}

    def on(self, event_type: str, callback):
        self.listeners.setdefault(event_type, []).append(callback)

    def emit(self, event_type: str, payload=None):
        for callback in self.listeners.get(event_type, []):
            callback(payload)

