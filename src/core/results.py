"""
Typed result formats for engine, agents, and tasks.
Ensures consistent output across all assistant operations.
"""

from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class AssistantResult:
    content: Any
    metadata: Optional[dict] = None

@dataclass
class AgentResult:
    agent: str
    output: Any
    metadata: Optional[dict] = None

@dataclass
class TaskResult:
    task_id: str
    status: str
    output: Optional[Any] = None
    metadata: Optional[dict] = None

