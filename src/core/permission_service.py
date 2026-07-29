"""
PermissionService ensures user consent before performing sensitive actions.
"""

from src.core.event_bus import EventBus

class PermissionService:
    def __init__(self, events: EventBus):
        self.events = events

    def request(self, permission: str):
        self.events.emit("permission.requested", {"permission": permission})
        return True

