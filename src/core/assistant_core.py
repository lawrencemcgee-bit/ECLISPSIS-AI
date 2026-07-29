"""
AssistantCore orchestrates conversation, agents, tasks, memory, and permissions.
This is the central facade used by the UI and API layers.
"""

from src.core.conversation_service import ConversationService
from src.core.agent_router import AgentRouter
from src.core.task_service import TaskService
from src.core.memory_service import MemoryService
from src.core.permission_service import PermissionService
from src.core.event_bus import EventBus
from src.services.onenote_service import OneNoteService
from src.services.weather_service import WeatherService
from src.services.news_service import NewsService
from src.agents.onenote_agent import OneNoteAgent
from src.agents.weather_agent import WeatherAgent
from src.agents.news_agent import NewsAgent


class AssistantCore:
    def __init__(self):
        self.events = EventBus()
        self.conversation = ConversationService(self.events)
        self.agents = AgentRouter(self.events)
        self.tasks = TaskService(self.events)
        self.memory = MemoryService()
        self.permissions = PermissionService(self.events)

    def process_message(self, message: str):
        """
        Main entry point for conversation.
        """
        return self.conversation.handle_message(message)

