"""
AssistantCore orchestrates conversation, agents, tasks, memory, permissions,
verification, tools, state transitions, persistence, logging, session restore,
auto-backup, crash recovery, multi-window persistence, and plugin execution.
"""

from src.core.conversation_service import ConversationService
from src.core.agent_router import AgentRouter
from src.core.task_service import TaskService
from src.core.memory_service import MemoryService
from src.core.permission_service import PermissionService
from src.core.verification_service import VerificationService
from src.core.event_bus import EventBus
from src.core.state_manager import StateManager
from src.core.state import AssistantState
from src.core.results import AssistantResult
from src.core.tool_registry import ToolRegistry
from src.core.persistence_service import PersistenceService
from src.core.logging_service import LoggingService
from src.core.user_profile_service import UserProfileService
from src.core.session_state_service import SessionStateService
from src.core.backup_service import BackupService
from src.plugins.plugin_manager import PluginManager


class AssistantCore:
    def __init__(self):
        self.events = EventBus()

        # Persistent settings
        self.persistence = PersistenceService()
        self.settings = self.persistence.load_settings()

        # Volatile session state
        self.session = SessionStateService()
        self.session_state = self.session.load()

        # User profile
        self.user_profile = UserProfileService()
        self.profile = self.user_profile.load()

        # Backup system
        self.backups = BackupService()

        # Plugin system
        self.plugins = PluginManager()

        # Logging
        self.logger = LoggingService()
        self.logger.info("startup", {
            "settings": self.settings,
            "profile": self.profile,
            "session": self.session_state,
            "plugins": self.plugins.list_plugins()
        })

        # Multi-window defaults
        self.session_state.setdefault("windows", {
            "logs":    {"x": 200, "y": 200, "w": 480, "h": 360, "open": False},
            "profile": {"x": 260, "y": 260, "w": 480, "h": 360, "open": False},
            "quick":   {"x": 320, "y": 320, "w": 480, "h": 360, "open": False}
        })

        # Recovery from corruption
        self.recover_if_corrupt()

        # Core subsystems
        self.conversation = ConversationService(self.events)
        self.agents = AgentRouter(self.events)
        self.tasks = TaskService(self.events)
        self.memory = MemoryService()
        self.permissions = PermissionService(self.events)
        self.verification = VerificationService(self.permissions)
        self.tools = ToolRegistry()
        self.state_manager = StateManager(self.events)

        self._register_builtin_agents()
        self._register_builtin_tools()

    # ---------------------------------------------------------
    # Agent Registration
    # ---------------------------------------------------------
    def _register_builtin_agents(self):
        from src.services.onenote_service import OneNoteService
        from src.services.weather_service import WeatherService
        from src.services.news_service import NewsService

        from src.agents.onenote_agent import OneNoteAgent
        from src.agents.weather_agent import WeatherAgent
        from src.agents.news_agent import NewsAgent

        self.agents.registry.register("onenote", OneNoteAgent(OneNoteService()))
        self.agents.registry.register("weather", WeatherAgent(WeatherService()))
        self.agents.registry.register("news", NewsAgent(NewsService()))

        self.logger.info("agents.registered", {"agents": ["onenote", "weather", "news"]})

    # ---------------------------------------------------------
    # Tool Registration
    # ---------------------------------------------------------
    def _register_builtin_tools(self):
        self.tools.register("echo", lambda text: {"echo": text})
        self.logger.info("tools.registered", {"tools": ["echo"]})

    # ---------------------------------------------------------
    # Persistence Hooks + Backups
    # ---------------------------------------------------------
    def save_settings(self):
        self.persistence.save_settings(self.settings)
        self.backups.backup_file("settings.json")
        self.logger.info("settings.saved", {"settings": self.settings})

    def save_chat(self, chat_list):
        self.persistence.save_chat_history(chat_list)
        self.backups.backup_file("chat_history.json")
        self.logger.info("chat.saved", {"count": len(chat_list)})

    def save_profile(self):
        self.user_profile.save(self.profile)
        self.backups.backup_file("user_profile.json")
        self.logger.info("profile.saved", {"profile": self.profile})

    def save_session(self):
        self.session.save(self.session_state)
        self.backups.backup_file("session_state.json")
        self.logger.info("session.saved", {"session": self.session_state})

    # ---------------------------------------------------------
    # Crash Recovery
    # ---------------------------------------------------------
    def mark_crash(self):
        self.session_state["crashed"] = True
        self.save_session()

    def recover_if_corrupt(self):
        try:
            _ = self.settings["window"]
            _ = self.profile["name"]
            _ = self.session_state["panels"]
        except Exception:
            self.logger.warn("recovery.triggered", {})
            self.backups.restore_latest("settings.json")
            self.backups.restore_latest("user_profile.json")
            self.backups.restore_latest("session_state.json")
            self.session_state["crashed"] = True
            self.save_session()

    # ---------------------------------------------------------
    # Multi-window persistence
    # ---------------------------------------------------------
    def save_window_state(self, name, state):
        self.session_state["windows"][name] = state
        self.save_session()

    # ---------------------------------------------------------
    # Plugin System
    # ---------------------------------------------------------
    def execute_plugin(self, plugin_id, payload):
        result = self.plugins.execute(plugin_id, payload)
        self.logger.info("plugin.execute", {
            "plugin": plugin_id,
            "payload": payload,
            "result": result
        })
        return result

    def list_plugins(self):
        return self.plugins.list_plugins()

    def set_plugin_enabled(self, plugin_id, value):
        self.plugins.set_enabled(plugin_id, value)
        self.logger.info("plugin.toggle", {"plugin": plugin_id, "enabled": value})

    # ---------------------------------------------------------
    # Conversation Processing
    # ---------------------------------------------------------
    def process_message(self, message: str) -> AssistantResult:
        self.logger.info("conversation.input", {"message": message})

        if not self.verification.verify("conversation", {"requires_permission": False}):
            self.logger.warn("conversation.blocked", {"reason": "safety_rules"})
            return AssistantResult(content="Action blocked by safety rules.")

        try:
            self.state_manager.set(AssistantState.LISTENING)
            self.state_manager.set(AssistantState.THINKING)

            result = self.conversation.handle_message(message)
            self.logger.info("conversation.output", {"content": result.content})

            self.state_manager.set(AssistantState.SPEAKING)
            self.state_manager.set(AssistantState.IDLE)

            return result

        except Exception as exc:
            self.logger.exception("conversation.error", exc)
            self.state_manager.set(AssistantState.ERROR)
            return AssistantResult(content="An internal error occurred. Check logs/app.log.")
