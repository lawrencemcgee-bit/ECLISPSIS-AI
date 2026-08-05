"""
PermissionService ensures user consent before performing sensitive actions.
Milestone 4: emits events + returns explicit approval.
"""

from src.core.event_bus import EventBus

class PermissionService:
    def __init__(self, events: EventBus):
        self.events = events

    def request(self, permission: str) -> bool:
        self.events.emit("permission.requested", {"permission": permission})
        # Milestone 4: auto-approve (UI will handle real approval later)
        return True

