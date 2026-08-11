"""
Lyra (Approach 2) — voice-first command console.

**Parity update**: previously a deliberately lighter build than Nova's
app.py — a static avatar, default chat bubbles, no waveform, width/height
-only window restore. This pass brings Lyra to feature parity with Nova
while keeping its own distinct design language (monospace terminal,
slash commands, warm amber palette) rather than becoming a reskin of
Nova's layout. What's now equivalent between the two personas:

- Reactive avatar (avatar.py) reacting to AssistantCore state, same as
  Nova's orb — lighter visual treatment (no glow layer), matching
  theme.py's "minimal chrome" intent.
- Waveform wired to AudioService.get_samples() (waveform.py), sized for
  the command bar instead of a centerpiece.
- Console-styled transcript (transcript.py) via FletBridge's
  bubble_builder hook, instead of reusing Nova's chat bubbles.
- Full window geometry restore (position + maximized, not just size).
- Settings (voice/rate) and permissions dialogs in the header.
- A tool-trigger tray with the same tap-to-flash feedback as Nova's,
  alongside (not replacing) the existing slash-command convention —
  two ways to reach the same three agents, matching how Lyra already
  offered both typed messages and slash commands.

Confidence: MEDIUM, same caveats as Nova (unexecuted, reviewed against
Flet ~0.86 docs).
"""

import asyncio

import flet as ft

from src.ui_flet.bridge import FletBridge
from src.ui_flet.personas.lyra import theme
from src.ui_flet.personas.lyra.avatar import build_avatar
from src.ui_flet.personas.lyra.waveform import build_waveform
from src.ui_flet.personas.lyra.transcript import build_console_line
from src.ui_flet.personas.lyra.permissions_dialog import build_permissions_button
from src.ui_flet.personas.lyra.settings_dialog import build_settings_button

AGENT_COMMANDS = {
    "notes": "onenote",
    "weather": "weather",
    "news": "news",
}

AGENTS = [
    ("onenote", ft.Icons.NOTE_ALT_OUTLINED, "Notes"),
    ("weather", ft.Icons.WB_SUNNY_OUTLINED, "Weather"),
    ("news", ft.Icons.NEWSPAPER_OUTLINED, "News"),
]


def create_lyra_app(assistant):
    def main(page: ft.Page):
        page.title = "LYRA — ECLIPSIS-AI"
        page.bgcolor = theme.BACKGROUND
        page.theme = theme.page_theme()
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20

        # Full restore of the previous session's window geometry — Lyra
        # previously only restored width/height, same gap Nova had before
        # its Tier 1 fix. x/y/maximized were already being saved by
        # save_window_geometry() (shared in FletBridge, not persona-
        # specific) but never read back for Lyra.
        window_settings = assistant.settings.get("window", {})
        page.window.width = window_settings.get("width", 900)
        page.window.height = window_settings.get("height", 640)
        page.window.left = window_settings.get("x", 100)
        page.window.top = window_settings.get("y", 100)
        page.window.maximized = window_settings.get("maximized", False)

        bridge = FletBridge(page, assistant)

        # ---------------------------------------------------------
        # Avatar (now reactive — see avatar.py)
        # ---------------------------------------------------------
        avatar = build_avatar(page)
        header = ft.Row(
            controls=[
                avatar,
                ft.Text("LYRA", size=20, color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                build_settings_button(page, assistant),
                build_permissions_button(page, assistant),
            ],
            spacing=12,
        )

        # ---------------------------------------------------------
        # Tool tray — same tap-to-flash pattern as Nova's, alongside
        # the existing slash-command convention, not replacing it.
        # ---------------------------------------------------------
        def make_agent_button(agent_id, icon, label):
            button = ft.IconButton(icon=icon, icon_color=theme.ACCENT, tooltip=f"{label} (/{label.lower()})")

            async def _flash():
                # run_selected_agent() is synchronous — same reasoning as
                # Nova's tool tray (nova/app.py): purely a visual
                # confirmation, not covering any actual wait.
                button.icon_color = ft.Colors.WHITE
                button.update()
                await asyncio.sleep(0.4)
                button.icon_color = theme.ACCENT
                button.update()

            def on_click(e):
                bridge.select_agent(agent_id)
                bridge.run_selected_agent()
                page.run_task(_flash)

            button.on_click = on_click
            return button

        tool_tray = theme.console_panel(
            ft.Row(
                controls=[make_agent_button(*a) for a in AGENTS],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
            ),
        )

        # ---------------------------------------------------------
        # Transcript (now console-styled via transcript.py, instead of
        # reusing FletBridge's default chat bubbles)
        # ---------------------------------------------------------
        chat_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        typing_indicator = ft.Text("lyra is processing…", color=theme.TEXT_MUTED,
                                    font_family=theme.CONSOLE_FONT, visible=False)

        transcript = theme.console_panel(
            ft.Column(controls=[
                ft.Container(content=chat_list, expand=True),
                typing_indicator,
            ], expand=True),
            expand=True,
        )

        # ---------------------------------------------------------
        # Command bar (now with a waveform meter next to the mic)
        # ---------------------------------------------------------
        command_field = ft.TextField(
            hint_text="> type a command or message",
            expand=True,
            border_color=theme.PANEL_BORDER,
            color=theme.TEXT_PRIMARY,
            text_style=ft.TextStyle(font_family=theme.CONSOLE_FONT),
            on_submit=lambda e: _submit(),
        )

        def _submit():
            text = command_field.value
            command_field.value = ""
            command_field.update()
            if not text:
                return
            # Slash-command convention for direct agent invocation, e.g.
            # "/weather" — anything else goes to process_message(), the
            # same as typed messages. Two different UX philosophies
            # (typed commands here, tap-driven tray above) over the same
            # underlying capability.
            if text.startswith("/"):
                agent_id = AGENT_COMMANDS.get(text[1:].strip().lower())
                if agent_id:
                    bridge.select_agent(agent_id)
                    bridge.run_selected_agent()
                    return
            bridge.send_message(text)

        waveform = build_waveform()

        mic_button = ft.IconButton(
            icon=ft.Icons.MIC_OUTLINED,
            icon_color=theme.ACCENT,
            selected_icon=ft.Icons.MIC,
            selected_icon_color=theme.DANGER,
            on_click=lambda e: (bridge.toggle_mic(), avatar.set_state("listening" if assistant.audio.active else "idle")),
            tooltip="Toggle microphone",
        )

        command_bar = theme.console_panel(
            ft.Column(controls=[
                ft.Row(controls=[mic_button, command_field]),
                waveform,
            ], spacing=4),
        )

        # ---------------------------------------------------------
        # Wire it together
        # ---------------------------------------------------------
        bridge.attach(
            chat_list=chat_list,
            typing_indicator=typing_indicator,
            waveform=waveform,
            mic_button=mic_button,
            on_state_changed_ui=avatar.set_state,
            bubble_builder=build_console_line,
        )
        avatar.start_pulse()

        def on_window_event(e: ft.WindowEvent):
            # Same reasoning as Nova's app.py: save unconditionally on
            # every window event rather than enumerating exact
            # WindowEventType names for maximize/restore that weren't
            # independently confirmed.
            bridge.save_window_geometry()
        page.window.on_event = on_window_event

        page.add(
            ft.Column(
                controls=[
                    header,
                    ft.Container(height=12),
                    tool_tray,
                    ft.Container(height=12),
                    transcript,
                    command_bar,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            )
        )

        bridge.scroll_chat_to_end_now()

    return main
