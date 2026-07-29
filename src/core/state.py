"""
Defines the unified assistant state model used across UI, engine, and services.
"""

from enum import Enum

class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    WORKING = "working"
    SPEAKING = "speaking"
    ERROR = "error"

