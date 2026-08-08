"""
AssistantCore orchestrates conversation, agents, tasks, memory, permissions,
verification, tools, state transitions, persistence, logging, session restore,
auto-backup, crash recovery, and multi-window persistence.
"""
import threading

from src.core.conversation_service import ConversationService
from src.core.agent_router import AgentRouter
from src.core.task_service import TaskService
from src.core.automation_service import AutomationService
from src.core.memory_service import MemoryService
from src.core.permission_service import PermissionService
from src.core.verification_service import VerificationService
from src.core.event_bus import EventBus
from src.core.observability import ObservabilityService
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

        # Observability (Phase 9): subscribes to the event bus immediately,
        # before any other subsystem is constructed, so it never misses an
        # event emitted during startup.
        self.observability = ObservabilityService(self.events)

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
        self.automation = AutomationService(self.events, self._execute_automation_action, self.persistence)
        self._ticker_thread = None
        self._ticker_stop_event = None
        self.memory = MemoryService(self.persistence)
        self.permissions = PermissionService(self.events, self.persistence)
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
        # Phase 10: camera access is permission-gated (see SafetyRules) and
        # fails closed until granted — previously this ran unconditionally.
        if not self.verification.verify("access_camera", {}):
            self.logger.warn("vision.blocked", {"reason": "permission_denied"})
            self.events.emit("vision.blocked", {"reason": "permission_denied"})
            return None
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
        audio subsystem and the event flow itself.

        Phase 10: turning the mic ON is permission-gated (see SafetyRules)
        and fails closed until granted — previously this started
        unconditionally. Turning it OFF is never gated; stopping capture
        is always safe to allow."""
        if not self.audio.active:
            if not self.verification.verify("access_microphone", {}):
                self.logger.warn("audio.blocked", {"reason": "permission_denied"})
                self.events.emit("audio.blocked", {"reason": "permission_denied"})
                return self.audio.active
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
    # Automation & Proactive Assistance (Phase 12)
    # ---------------------------------------------------------
    def _execute_automation_action(self, action: dict):
        """Resolves a declarative automation action into a call against an
        existing capability, so an automated trigger can only do what a
        manual request could already do — inheriting whatever
        verification/permission checks that capability already has,
        rather than automation becoming a separate, less-guarded path."""
        action_type = action.get("type")

        if action_type == "agent":
            result = self.agents.run(action["agent"], **action.get("kwargs", {}))
            if result.metadata and result.metadata.get("error"):
                raise RuntimeError(result.metadata["error"])
            return result

        if action_type == "plugin":
            return self.execute_plugins(action["plugin_id"], action.get("payload", {}))

        if action_type == "message":
            return self.process_message(action["text"])

        if action_type == "notify":
            # A proactive suggestion with nothing to execute — just surface
            # it for the UI to display.
            text = action["text"]
            self.events.emit("automation.notification", {"text": text})
            return {"notified": True, "text": text}

        raise ValueError(f"Unknown automation action type: {action_type!r}")

    def register_event_automation(self, event_name, action, predicate=None,
                                   trigger_id=None, persistent=False):
        return self.automation.register_event_trigger(
            event_name, action, predicate, trigger_id, persistent
        )

    def register_schedule_automation(self, interval_seconds, action, trigger_id=None,
                                      run_immediately=False, persistent=True):
        return self.automation.register_schedule_trigger(
            interval_seconds, action, trigger_id, run_immediately, persistent
        )

    def unregister_automation(self, trigger_id):
        self.automation.unregister(trigger_id)

    def set_automation_enabled(self, trigger_id, enabled):
        self.automation.set_enabled(trigger_id, enabled)

    def list_automations(self):
        return self.automation.list_triggers()

    def automation_tick(self, now=None):
        """Fires any due schedule-based triggers. Call directly for
        deterministic testing; in a running process this is what
        start_automation_ticker() calls periodically."""
        return self.automation.tick(now)

    def start_automation_ticker(self, interval_seconds=30):
        """Phase 13 decision on how schedule-based triggers actually get
        checked in a running process: a plain daemon background thread
        that calls automation_tick() every interval_seconds, rather than
        a UI-framework-specific timer (e.g. Qt's QTimer). AssistantCore is
        shared across the desktop UI (qml_app.py) and the HTTP API
        (api.py) and shouldn't assume which one is hosting it — either
        entry point just calls this once at startup.

        Idempotent: calling this again stops any existing ticker first
        rather than stacking threads.
        """
        self.stop_automation_ticker()
        self._ticker_stop_event = threading.Event()

        def _loop():
            while not self._ticker_stop_event.wait(interval_seconds):
                try:
                    self.automation_tick()
                except Exception as exc:
                    self.logger.exception("automation.ticker_error", {"error": str(exc)})

        self._ticker_thread = threading.Thread(target=_loop, daemon=True, name="automation-ticker")
        self._ticker_thread.start()

    def stop_automation_ticker(self):
        if self._ticker_thread is not None and self._ticker_thread.is_alive():
            self._ticker_stop_event.set()
            self._ticker_thread.join(timeout=1)
        self._ticker_thread = None

    # ---------------------------------------------------------
    # Permissions & Safety (Phase 10)
    # ---------------------------------------------------------
    def grant_permission(self, permission: str):
        self.permissions.grant(permission)
        self.logger.info("permission.granted", {"permission": permission})

    def deny_permission(self, permission: str):
        self.permissions.deny(permission)
        self.logger.info("permission.denied", {"permission": permission})

    def revoke_permission(self, permission: str):
        self.permissions.revoke(permission)
        self.logger.info("permission.revoked", {"permission": permission})

    def list_permissions(self):
        return {
            "granted": sorted(self.permissions.granted),
            "denied": sorted(self.permissions.denied),
        }

    def set_permission_decision_handler(self, handler):
        """Wires an interactive approval callback (e.g. a QML dialog) into
        PermissionService. Pass None to go back to fail-closed-only."""
        self.permissions.set_decision_handler(handler)

    # ---------------------------------------------------------
    # Observability & Diagnostics (Phase 9)
    # ---------------------------------------------------------
    def get_diagnostics(self):
        """Aggregates per-subsystem health with ObservabilityService's
        counters/uptime/system metrics into one snapshot. AssistantCore
        supplies the per-subsystem health because it's the only thing that
        owns those subsystems and knows what "healthy" means for each —
        ObservabilityService just assembles what it's given.

        Vision/Voice/Audio are marked "simulated": true because they're
        still placeholder-level (Phase 6/7 note in their own modules) — a
        diagnostics panel should say so honestly rather than reporting
        green health for a camera/mic that was never actually opened.
        """
        subsystems = {
            "engine": {
                "healthy": self.state_manager.state != AssistantState.ERROR,
                "state": self.state_manager.state.value,
            },
            "voice": {
                "healthy": True,
                "listening": self.voice.listening,
                "simulated": True,
            },
            "vision": {
                "healthy": True,
                "simulated": True,
            },
            "audio": {
                "healthy": True,
                "active": self.audio.active,
                "simulated": True,
            },
            "plugins": {
                "healthy": True,
                "loaded": len(self.plugins.list_plugins()),
            },
            "security": {
                "healthy": True,
                "granted": len(self.permissions.granted),
                "denied": len(self.permissions.denied),
                "blocked_actions": len(self.verification.rules.blocked_actions),
                "interactive_handler_wired": self.permissions._decision_handler is not None,
            },
            "automation": {
                "healthy": True,
                "triggers": len(self.automation.triggers),
                "enabled": sum(1 for t in self.automation.triggers.values() if t["enabled"]),
            },
        }
        return self.observability.snapshot(subsystems)

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
