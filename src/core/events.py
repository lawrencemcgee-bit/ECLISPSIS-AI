"""
Typed event definitions for the unified event dispatcher.
These events will be emitted by engine, agents, voice, vision, and tasks.
"""

from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Event:
    type: str
    payload: Optional[Any] = None

