"""
AssistantCore orchestrates conversation, agents, tasks, memory, permissions,
verification, tools, state transitions, persistence, logging, session restore,
auto-backup, crash recovery, and multi-window persistence.
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
from src.services.vision_service import VisionService
from src.services.voice_service import VoiceService
from src.services.audio_service import AudioService
from src.services.nci_service import NCIService



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

        # Plugin manager
        self.plugins = PluginManager()

        # Logging
        self.logger = LoggingService()
        self.logger.info("startup", {
            "settings": self.settings,
            "profile": self.profile,
            "session": self.session_state
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
        self.memory = MemoryService(self.persistence)
        self.permissions = PermissionService(self.events)
        self.verification = VerificationService(self.permissions)
        self.tools = ToolRegistry()
        self.state_manager = StateManager(self.events)

        # Multimodal (Phase 6): previously VisionService/VoiceService were
        # never constructed anywhere, and AudioService was owned directly by
        # the UI layer (StateBridge), bypassing the event bus entirely —
        # inconsistent with how every other subsystem here is owned. Still
        # simulated/placeholder-level capture, same as before; only the
        # ownership and event integration changed.
        self.vision = VisionService()
        self.voice = VoiceService()
        self.audio = AudioService()
        self.nci = NCIService()
        if self.settings.get("mic_enabled", False):
            # Restored here now instead of in StateBridge's __init__, so
            # audio state restoration happens alongside every other
            # settings-driven restore that already happens at core startup.
            self.audio.start()

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
    # Plugin manager
    #----------------------------------------------------------
    def execute_plugins(self, plugin_id, payload):
        result = self.plugins.execute(plugin_id, payload)
        self.logger.info("execute_plugins", {"plugin_id": plugin_id, "payload": payload, "result": result})
        return result

    def list_plugins(self):
        result = self.plugins.list_plugins()
        return result

    def set_plugin_enabled(self, plugin_id, enabled):
        self.plugins.set_enabled(plugin_id, enabled)
        self.logger.info("plugin.toggle", {"plugin": plugin_id, "enabled": enabled})

    # ---------------------------------------------------------
    # Multimodal (Phase 6)
    # ---------------------------------------------------------
    def capture_vision(self):
        result = self.vision.capture()
        self.events.emit("vision.captured", {"result": result})
        self.logger.info("vision.captured", {"result": result})
        return result

    def start_voice_listening(self):
        changed = self.voice.start_listening()
        if changed:
            self.events.emit("voice.listening_started", {})
        return self.voice.listening

    def stop_voice_listening(self):
        changed = self.voice.stop_listening()
        if changed:
            self.events.emit("voice.listening_stopped", {})
        return self.voice.listening

    def voice_command_received(self, text: str):
        """Routes a recognized voice command through the same conversation
        pipeline as typed messages — once real STT exists, it only needs to
        call this method with the transcribed text; the rest of the
        pipeline (verification, conversation processing, logging) is
        already wired and tested via this path.
        Mirrors the graceful-degradation pattern used for agents/tools/tasks:
        rejects with a typed result instead of processing silently if voice
        input wasn't actually active."""
        if not self.voice.listening:
            self.events.emit("voice.command_rejected", {"reason": "not_listening"})
            return AssistantResult(content=None, metadata={"error": "not_listening"})
        self.events.emit("voice.command_received", {"text": text})
        return self.process_message(text)

    # ---------------------------------------------------------
    # NCI Analytics (Phase 8)
    # ---------------------------------------------------------
    def analyze(self, text: str):
        """Standalone, explicitly-invoked capability — not wired into
        process_message() automatically. No specification exists yet for
        what real analysis NCI should perform on every message, and
        forcing it into that pipeline now would be inventing a design
        decision rather than fixing a defect. Available for a future
        caller (a UI panel, an automation phase) to invoke directly."""
        self.events.emit("nci.analysis.started", {"text": text})
        result = self.nci.interpret(text)
        self.events.emit("nci.analysis.completed", {"result": result})
        self.logger.info("nci.analysis.completed", {"result": result})
        return result

    def toggle_mic(self):
        """Consolidates what StateBridge.toggleMic() used to do directly
        (start/stop AudioService + persist the setting) into the core, so
        the UI layer just asks for a state change instead of owning the
        audio subsystem and the event flow itself."""
        if not self.audio.active:
            self.audio.start()
            self.settings["mic_enabled"] = True
            self.events.emit("audio.started", {})
        else:
            self.audio.stop()
            self.settings["mic_enabled"] = False
            self.events.emit("audio.stopped", {})
        self.save_settings()
        return self.audio.active

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
