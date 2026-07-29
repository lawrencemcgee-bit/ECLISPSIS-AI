"""
StateManager tracks assistant state transitions and emits observability events.
"""

from src.core.state import AssistantState
from src.core.event_bus import EventBus

class StateManager:
    def __init__(self, events: EventBus):
        self.state = AssistantState.IDLE
        self.events = events

    def set(self, new_state: AssistantState):
        old = self.state
        self.state = new_state
        self.events.emit("state.changed", {"old": old.value, "new": new_state.value})

