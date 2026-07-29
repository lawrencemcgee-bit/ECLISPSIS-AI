"""
ConversationService handles message flow, engine routing, and agent invocation.
"""

from src.engine.local_engine import LocalEngine
from src.core.results import AssistantResult
from src.core.event_bus import EventBus

class ConversationService:
    def __init__(self, events: EventBus):
        self.engine = LocalEngine()
        self.events = events

    def handle_message(self, message: str) -> AssistantResult:
        self.events.emit("conversation.received", {"message": message})
        result = self.engine.process(message)
        self.events.emit("conversation.processed", {"result": result})
        return result

