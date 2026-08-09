"""
FletBridge — the Flet equivalent of src/ui/state_bridge.py's StateBridge.

Same job, different mechanism. StateBridge (PySide6/QML) worked by holding
Qt Signals that QML's declarative bindings subscribed to — a change on the
Python side triggered a Signal, and QML re-rendered automatically.

Flet has no declarative binding system reaching back into Python controls
the way QML does. Flet is imperative: you mutate a control's properties in
Python, then explicitly call that control's .update() (or page.update()
for everything at once). FletBridge reflects that — instead of emitting
Signals, it holds direct references to the Flet controls it's responsible
for and updates them in place after each AssistantCore call.

One genuine architectural win over the QML approach: main_window.qml
exposed the raw, non-QObject AssistantCore instance directly to QML via
setContextProperty(), which was flagged during Milestone 13 verification
as an unresolved risk — whether QML's meta-object system can reliably
read nested attributes off a plain Python object. That risk doesn't exist
here. Flet controls ARE Python objects; there's no separate JS/QML engine
attribute-marshalling layer to worry about. assistant.profile,
assistant.settings, etc. are just read directly.

Confidence note: the Flet API calls in this file (Page/Control properties,
event handler names like on_click, page.show_dialog(), page.run_task()) are
written against Flet ~0.86 (current as of Aug 2026) and reviewed
carefully, but never executed — there is no way to install/run Flet in
the sandbox this was written in. Flet is also mid a breaking rewrite
toward 1.0 as of this writing. Treat every Flet-specific call here as
"needs a real run to confirm," not as verified working code, the same
caveat already applied to the FastAPI layer (src/api/api_app.py) before
it was confirmed working in Milestone 11's follow-up.
"""

import asyncio
import json

import flet as ft


class FletBridge:
    def __init__(self, page: ft.Page, assistant):
        self.page = page
        self.assistant = assistant

        self.current_agent = assistant.settings.get("last_agent", "onenote")
        self._typing = False
        self._waveform_task = None
        self._voice_task = None

        # Controls the bridge updates directly. Each persona (Nova/Lyra)
        # builds its own visual tree and hands the specific controls it
        # wants driven by the bridge — the bridge doesn't build UI itself,
        # it only knows how to update whatever controls it's given. This
        # keeps FletBridge persona-agnostic, same as StateBridge was
        # QML-layout-agnostic.
        self.chat_list: ft.ListView | None = None
        self.typing_indicator: ft.Control | None = None
        self.waveform: ft.Control | None = None
        self.mic_button: ft.Control | None = None
        self.on_state_changed_ui = None  # optional callback(state_str) for persona-specific reactions (e.g. Nova's orb color)

        # Restore chat history (same persistence call StateBridge used).
        self._history = []
        for item in assistant.persistence.load_chat_history():
            self._history.append(item)

        # Restore session state (panels/draft) — read directly, no
        # marshalling concerns (see module docstring).
        self.session = assistant.session_state
        self.draft = self.session.get("draft", "")

        # Crash recovery toast, deferred until a persona attaches its
        # page (see attach()) since page.show_dialog() needs a mounted page.
        self._pending_crash_toast = assistant.session_state.get("crashed", False)
        if self._pending_crash_toast:
            assistant.session_state["crashed"] = False
            assistant.save_session()

        # Subscribe to the event bus for things the UI should react to
        # even when they didn't originate from a direct button press —
        # automation notifications, permission denials, errors. This is
        # the same category of thing StateBridge's toastRequested Signal
        # covered, just wired via assistant.events instead of a Qt Signal.
        assistant.events.on("state.changed", self._on_state_changed)
        assistant.events.on("automation.notification", self._on_automation_notification)
        assistant.events.on("vision.blocked", lambda p: self._toast("Camera access denied"))
        assistant.events.on("audio.blocked", lambda p: self._toast("Microphone access denied"))

    # ---------------------------------------------------------
    # Attachment — call once the persona has built its control tree
    # ---------------------------------------------------------
    def attach(self, chat_list, typing_indicator=None, waveform=None, mic_button=None, on_state_changed_ui=None):
        self.chat_list = chat_list
        self.typing_indicator = typing_indicator
        self.waveform = waveform
        self.mic_button = mic_button
        self.on_state_changed_ui = on_state_changed_ui

        for item in self._history:
            self.chat_list.controls.append(_chat_bubble(item["sender"], item["text"]))
        # NOT scrolling here: at this point in nova/app.py's setup,
        # page.add() hasn't run yet, so chat_list isn't actually mounted
        # into the page's control tree — scrolling an unmounted control
        # is a plausible source of a silent background-task exception.
        # nova/app.py calls scroll_chat_to_end_now() explicitly, after
        # page.add(), instead.

        if self._pending_crash_toast:
            self._toast("Recovered from previous crash")
            self._pending_crash_toast = False

        # AssistantCore restores mic-on/off state from settings at
        # startup (see AssistantCore.__init__'s mic_enabled restore) —
        # but that happens before any UI exists to reflect it. Without
        # this, the mic button always displayed as "off" regardless of
        # whether audio was actually already active, so a first click
        # after a restart where the mic was previously left on would
        # silently turn it OFF instead of on. Sync both the button's
        # visual state and the background tasks (waveform, voice loop)
        # that toggle_mic() would otherwise be the only thing to start.
        if self.assistant.audio.active:
            if self.mic_button is not None:
                self.mic_button.selected = True
            self._start_waveform_task()
            # voice.listening is never persisted (only audio.active is —
            # see AssistantCore.__init__), so a restored-active mic needs
            # this explicitly, not just a check against a flag that would
            # always be False on a fresh AssistantCore regardless of the
            # restore. Keeps the restore consistent with what
            # toggle_mic() does when a user turns the mic on normally —
            # both audio capture and voice listening together, not one
            # without the other.
            self.assistant.start_voice_listening()
            self._start_voice_loop_task()

        self.page.update()

    # ---------------------------------------------------------
    # Event bus reactions
    # ---------------------------------------------------------
    def _on_state_changed(self, payload):
        new_state = payload.get("new") if payload else None
        if new_state is None:
            return
        self._set_typing(new_state == "thinking")
        if self.on_state_changed_ui:
            self.on_state_changed_ui(new_state)
        if new_state == "error":
            self._toast("An internal error occurred")

    def _on_automation_notification(self, payload):
        self._toast(payload.get("text", ""))

    def _set_typing(self, value: bool):
        if self._typing == value:
            return
        self._typing = value
        if self.typing_indicator is not None:
            self.typing_indicator.visible = value
            self.typing_indicator.update()

    def _toast(self, text: str):
        # Confirmed via runtime error: page.open() doesn't exist on this
        # Page object. Using the other candidate found earlier.
        self.page.show_dialog(ft.SnackBar(content=ft.Text(text)))

    # ---------------------------------------------------------
    # Chat
    # ---------------------------------------------------------
    def _push_chat(self, sender, text):
        self.chat_list.controls.append(_chat_bubble(sender, text))
        self.chat_list.update()
        # scroll_to() is async in this Flet version — confirmed by a real
        # RuntimeWarning ("coroutine was never awaited") from calling it
        # as if it were synchronous, which silently did nothing. _push_chat()
        # is called from both sync contexts (send_message, from on_click/
        # on_submit handlers) and async ones (_voice_loop); making this
        # method itself async would cascade through every caller. Firing
        # the coroutine via page.run_task() avoids that — it schedules
        # the scroll on the page's event loop without requiring the
        # caller to await anything.
        self.page.run_task(self._scroll_chat_to_end)

        items = self._history + [{"sender": sender, "text": text}]
        self._history = items
        self.assistant.save_chat(items)

    async def _scroll_chat_to_end(self):
        await self.chat_list.scroll_to(offset=-1, duration=200)

    def scroll_chat_to_end_now(self):
        """Call after page.add() — see attach()'s comment on why the
        initial-history scroll can't safely happen from inside attach()
        itself."""
        if self.chat_list is not None:
            self.page.run_task(self._scroll_chat_to_end)

    def send_message(self, text: str):
        if not text.strip():
            return
        self._push_chat("user", text)
        result = self.assistant.process_message(text)
        self._push_chat("assistant", result.content)

    # ---------------------------------------------------------
    # Agents
    # ---------------------------------------------------------
    def select_agent(self, agent_name: str):
        self.current_agent = agent_name
        self.assistant.settings["last_agent"] = agent_name
        self.assistant.save_settings()
        self._toast(f"Agent switched to {agent_name}")

    def run_selected_agent(self):
        agent_kwargs = {
            "onenote": {"action": "open", "page": "daily"},
            "weather": {"location": "San Antonio"},
            "news": {"category": "technology"},
        }.get(self.current_agent)

        if agent_kwargs is None:
            self._push_chat("system", f"Unknown agent: {self.current_agent}")
            return

        agent_result = self.assistant.agents.run(self.current_agent, **agent_kwargs)
        if agent_result.metadata and agent_result.metadata.get("error"):
            result = f"Agent error: {agent_result.metadata['error']}"
        else:
            result = agent_result.output

        self._push_chat(self.current_agent, str(result))

    # ---------------------------------------------------------
    # Microphone / waveform
    # ---------------------------------------------------------
    def toggle_mic(self):
        active = self.assistant.toggle_mic()

        # Phase 6 built voice.listening and audio.active as two separate
        # concepts; real voice command flow needs both true together, so
        # the mic button now drives both rather than just audio capture.
        if active:
            self.assistant.start_voice_listening()
        else:
            self.assistant.stop_voice_listening()

        self._toast("Microphone enabled" if active else "Microphone disabled")

        if self.mic_button is not None:
            self.mic_button.selected = active
            self.mic_button.update()

        if active:
            self._start_waveform_task()
            self._start_voice_loop_task()
        else:
            self._stop_waveform_task()
            self._stop_voice_loop_task()
        return active

    def _start_voice_loop_task(self):
        if self._voice_task is not None:
            return
        self._voice_task = self.page.run_task(self._voice_loop)

    def _stop_voice_loop_task(self):
        if self._voice_task is not None:
            self._voice_task.cancel()
            self._voice_task = None

    async def _voice_loop(self):
        """Polls process_voice_audio() while both audio capture and voice
        listening are active. Most calls return None (mid-utterance —
        that's the normal, expected case, not a failure); only a
        finalized utterance produces something to push into chat. On a
        genuine recognized command, also speaks the reply aloud if TTS is
        available — completing the voice-in/voice-out loop, not just
        voice-in."""
        try:
            while self.assistant.audio.active and self.assistant.voice.listening:
                outcome = self.assistant.process_voice_audio()
                if outcome is not None:
                    self._push_chat("user", outcome["text"])
                    reply = outcome["result"]
                    if reply.content:
                        self._push_chat("assistant", reply.content)
                        self.assistant.speak(reply.content)
                await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            pass

    def capture_vision(self):
        """Camera access is permission-gated the same way toggle_mic() is
        (Phase 10) — AssistantCore.capture_vision() returns None on denial
        and already emits "vision.blocked", which __init__ subscribes to
        for the toast. This just handles the success case: push the
        result into chat like an agent response."""
        result = self.assistant.capture_vision()
        if result is not None:
            self._push_chat("vision", str(result))
        return result

    def _start_waveform_task(self):
        if self._waveform_task is not None or self.waveform is None:
            return
        # page.run_task schedules a coroutine on the page's own asyncio
        # event loop — the Flet-idiomatic replacement for a QML Timer.
        # Distinct from AssistantCore.start_automation_ticker(), which is
        # a plain background thread for the 30s-interval automation
        # checks; this needs a much tighter loop (waveform refresh), so it
        # rides Flet's own loop instead of spawning a second thread.
        self._waveform_task = self.page.run_task(self._waveform_loop)

    def _stop_waveform_task(self):
        if self._waveform_task is not None:
            self._waveform_task.cancel()
            self._waveform_task = None

    async def _waveform_loop(self):
        try:
            while self.assistant.audio.active:
                samples = self.assistant.audio.get_samples()
                self._render_waveform(samples)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    def _render_waveform(self, samples):
        """Persona-specific rendering is injected via self.waveform being
        whatever control the persona built (a bar chart Row, a custom
        Canvas, etc.) — this just hands it the data and updates it. Left
        deliberately generic here; see each persona's waveform module for
        the actual visual."""
        if hasattr(self.waveform, "set_samples"):
            self.waveform.set_samples(samples)
        self.waveform.update()

    # ---------------------------------------------------------
    # Window + session persistence
    # ---------------------------------------------------------
    def save_window_geometry(self):
        # page.window.width/height/left/top/maximized is the current
        # (~0.8x) Page window API; earlier Flet versions used
        # page.window_width etc. as flat Page attributes. Confirm against
        # the installed version — this is one of the more version-churned
        # corners of Flet's API.
        w = self.assistant.settings["window"]
        w["width"] = self.page.window.width
        w["height"] = self.page.window.height
        w["x"] = self.page.window.left
        w["y"] = self.page.window.top
        w["maximized"] = self.page.window.maximized
        self.assistant.save_settings()

    def update_draft(self, text: str):
        self.assistant.session_state["draft"] = text
        self.assistant.save_session()

    def set_panel_open(self, panel_name: str, value: bool):
        self.assistant.session_state["panels"][panel_name] = value
        self.assistant.save_session()

    # ---------------------------------------------------------
    # Plugins
    # ---------------------------------------------------------
    def list_plugins(self):
        return self.assistant.list_plugins()

    def execute_plugin(self, plugin_id: str, payload: dict):
        result = self.assistant.execute_plugins(plugin_id, payload)
        return result

    def set_plugin_enabled(self, plugin_id: str, value: bool):
        self.assistant.set_plugin_enabled(plugin_id, value)


def _chat_bubble(sender: str, text: str) -> ft.Control:
    """Shared bubble builder so both personas render chat history
    identically even if their surrounding chrome differs. Personas that
    want a different bubble style can pass their own builder into
    FletBridge instead — left simple here deliberately; see each
    persona's theme module for where to hook a custom look."""
    is_user = sender == "user"
    return ft.Row(
        alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
        controls=[
            ft.Container(
                content=ft.Text(text, selectable=True),
                bgcolor=ft.Colors.BLUE_700 if is_user else ft.Colors.GREY_800,
                border_radius=12,
                padding=12,
                width=420,
            )
        ],
    )
