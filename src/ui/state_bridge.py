from PySide6.QtCore import QObject, Signal, Slot, Property, QAbstractListModel, QModelIndex, Qt
from src.core.state import AssistantState
from src.services.audio_service import AudioService
import json

class ChatModel(QAbstractListModel):
    ROLE_TEXT = Qt.UserRole + 1
    ROLE_SENDER = Qt.UserRole + 2

    def __init__(self):
        super().__init__()
        self._items = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        if role == ChatModel.ROLE_TEXT:
            return item["text"]
        if role == ChatModel.ROLE_SENDER:
            return item["sender"]
        return None

    def roleNames(self):
        return {
            ChatModel.ROLE_TEXT: b"text",
            ChatModel.ROLE_SENDER: b"sender",
        }

    def addMessage(self, sender, text):
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append({"sender": sender, "text": text})
        self.endInsertRows()


class StateBridge(QObject):
    stateChanged = Signal(str)
    waveformUpdated = Signal(list)
    outputUpdated = Signal(str)
    typingChanged = Signal(bool)
    toastRequested = Signal(str)

    # Pop-out windows
    openLogsWindow = Signal()
    openProfileWindow = Signal()
    openQuickWindow = Signal()

    # Plugin system
    pluginListUpdated = Signal()
    pluginExecuted = Signal(str)

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.audio = AudioService()
        self.chatModel = ChatModel()
        self.current_agent = assistant.settings.get("last_agent", "onenote")
        self.waveform_counter = 0
        self._typing = False

        # Load chat history
        history = assistant.persistence.load_chat_history()
        for item in history:
            self.chatModel.addMessage(item["sender"], item["text"])

        # Load session state
        self.session = assistant.session_state

        self.settings_open = self.session["panels"]["settings"]
        self.profile_open = self.session["panels"]["profile"]
        self.logs_open = self.session["panels"]["logs"]
        self.quick_open = self.session["panels"]["quick"]

        self.draft = self.session["draft"]

        # Crash recovery toast
        if self.assistant.session_state.get("crashed", False):
            self.toastRequested.emit("Recovered from previous crash")
            self.assistant.session_state["crashed"] = False
            self.assistant.save_session()

        # Restore mic state
        if assistant.settings.get("mic_enabled", False):
            self.audio.start()

    # ---------------------------------------------------------
    # Typing Indicator
    # ---------------------------------------------------------
    def update_from_core(self, new_state: AssistantState):
        self.stateChanged.emit(new_state.value)
        if new_state == AssistantState.THINKING:
            self._set_typing(True)
        elif new_state in (AssistantState.SPEAKING, AssistantState.IDLE, AssistantState.ERROR):
            self._set_typing(False)
        if new_state == AssistantState.ERROR:
            self.toastRequested.emit("An internal error occurred")

    def _set_typing(self, value: bool):
        if self._typing != value:
            self._typing = value
            self.typingChanged.emit(self._typing)

    @Property(bool, notify=typingChanged)
    def typing(self):
        return self._typing

    # ---------------------------------------------------------
    # Chat Handling
    # ---------------------------------------------------------
    def _push_chat(self, sender, text):
        self.chatModel.addMessage(sender, text)

        if sender == "assistant":
            self.outputUpdated.emit("__play_reply_sound__")

        items = [{"sender": i["sender"], "text": i["text"]} for i in self.chatModel._items]
        self.assistant.save_chat(items)

    @Slot(str)
    def sendMessage(self, text: str):
        self.outputUpdated.emit("__play_send_sound__")

        self._push_chat("user", text)
        result = self.assistant.process_message(text)
        self._push_chat("assistant", result.content)
        self.outputUpdated.emit(result.content)

    # ---------------------------------------------------------
    # Agent Selection
    # ---------------------------------------------------------
    @Slot(str)
    def selectAgent(self, agent_name: str):
        self.current_agent = agent_name
        self.assistant.settings["last_agent"] = agent_name
        self.assistant.save_settings()
        self.toastRequested.emit("Agent switched to " + agent_name)

    @Slot()
    def runSelectedAgent(self):
        agent = self.assistant.agents.registry.get(self.current_agent)
        if not agent:
            self._push_chat("system", f"Unknown agent: {self.current_agent}")
            return

        if self.current_agent == "onenote":
            result = agent.open("daily").output
        elif self.current_agent == "weather":
            result = agent.get("San Antonio").output
        elif self.current_agent == "news":
            result = agent.get("technology").output
        else:
            result = "Unknown agent."

        self._push_chat(self.current_agent, str(result))
        self.outputUpdated.emit(str(result))

    # ---------------------------------------------------------
    # Microphone
    # ---------------------------------------------------------
    @Slot()
    def toggleMic(self):
        if not self.audio.active:
            self.audio.start()
            self.assistant.settings["mic_enabled"] = True
            self.toastRequested.emit("Microphone enabled")
        else:
            self.audio.stop()
            self.assistant.settings["mic_enabled"] = False
            self.toastRequested.emit("Microphone disabled")
        self.assistant.save_settings()

    @Slot()
    def updateWaveform(self):
        if not self.audio.active:
            return

        self.waveform_counter += 1
        if self.waveform_counter % 3 != 0:
            return

        samples = self.audio.get_samples()
        self.waveformUpdated.emit(samples)

    # ---------------------------------------------------------
    # Window Persistence
    # ---------------------------------------------------------
    @Slot(int, int)
    def updateWindowSize(self, width: int, height: int):
        self.assistant.settings["window"]["width"] = width
        self.assistant.settings["window"]["height"] = height
        self.assistant.save_settings()

    @Slot(int, int)
    def updateWindowPosition(self, x: int, y: int):
        self.assistant.settings["window"]["x"] = x
        self.assistant.settings["window"]["y"] = y
        self.assistant.save_settings()

    @Slot(bool)
    def updateWindowMaximized(self, maximized: bool):
        self.assistant.settings["window"]["maximized"] = maximized
        self.assistant.save_settings()

    # ---------------------------------------------------------
    # Session State (Panels + Draft)
    # ---------------------------------------------------------
    @Slot(bool)
    def setSettingsOpen(self, value):
        self.assistant.session_state["panels"]["settings"] = value
        self.assistant.save_session()

    @Slot(bool)
    def setProfileOpen(self, value):
        self.assistant.session_state["panels"]["profile"] = value
        self.assistant.save_session()

    @Slot(bool)
    def setLogsOpen(self, value):
        self.assistant.session_state["panels"]["logs"] = value
        self.assistant.save_session()

    @Slot(bool)
    def setQuickOpen(self, value):
        self.assistant.session_state["panels"]["quick"] = value
        self.assistant.save_session()

    @Slot(str)
    def updateDraft(self, text):
        self.assistant.session_state["draft"] = text
        self.assistant.save_session()

    # ---------------------------------------------------------
    # Pop-out Windows
    # ---------------------------------------------------------
    @Slot()
    def popLogs(self):
        self.openLogsWindow.emit()
        self.assistant.session_state["windows"]["logs"]["open"] = True
        self.assistant.save_session()

    @Slot()
    def popProfile(self):
        self.openProfileWindow.emit()
        self.assistant.session_state["windows"]["profile"]["open"] = True
        self.assistant.save_session()

    @Slot()
    def popQuick(self):
        self.openQuickWindow.emit()
        self.assistant.session_state["windows"]["quick"]["open"] = True
        self.assistant.save_session()

    @Slot(str, int, int, int, int)
    def updateWindowGeometry(self, name, x, y, w, h):
        self.assistant.session_state["windows"][name] = {
            "x": x, "y": y, "w": w, "h": h,
            "open": True
        }
        self.assistant.save_session()

    # ---------------------------------------------------------
    # Plugin System
    # ---------------------------------------------------------
    @Slot()
    def refreshPlugins(self):
        self.pluginListUpdated.emit()

    @Slot(str, str)
    def executePlugin(self, plugin_id, payload):
        result = self.assistant.execute_plugin(plugin_id, payload)
        self.pluginExecuted.emit(json.dumps(result))

    @Slot(str, bool)
    def setPluginEnabled(self, plugin_id, value):
        self.assistant.set_plugin_enabled(plugin_id, value)
        self.refreshPlugins()

    # ---------------------------------------------------------
    # Profile Exposure
    # ---------------------------------------------------------
    @Property('QVariant')
    def profile(self):
        return self.assistant.profile

    # ---------------------------------------------------------
    # Chat Model Exposure
    # ---------------------------------------------------------
    @Property(QObject)
    def chat(self):
        return self.chatModel
