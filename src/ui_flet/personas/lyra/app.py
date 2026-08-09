"""
Lyra (Approach 2) — voice-first command console.

Deliberately a lighter build than Nova's app.py: a static avatar circle
(no continuous pulse task), a monospace scrolling transcript styled like
a terminal, and a single command bar that doubles as text input and mic
trigger. This is a genuine, distinct design direction — not Nova with
different colors — but it stops short of Nova's animation depth and
per-message styling. Bringing it to full parity (state-reactive avatar,
richer transcript formatting, a dedicated tool-trigger area) is
straightforward from here using the same patterns Nova's app.py/orb.py
already demonstrate — flagged as a deliberate scope cut for this pass,
not a limitation of the approach itself.

Confidence: MEDIUM, same caveats as Nova (unexecuted, reviewed against
Flet ~0.86 docs).
"""

import flet as ft

from src.ui_flet.bridge import FletBridge
from src.ui_flet.personas.lyra import theme

AGENT_COMMANDS = {
    "notes": "onenote",
    "weather": "weather",
    "news": "news",
}


def create_lyra_app(assistant):
    def main(page: ft.Page):
        page.title = "LYRA — ECLIPSIS-AI"
        page.bgcolor = theme.BACKGROUND
        page.theme = theme.page_theme()
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window.width = assistant.settings.get("window", {}).get("width", 900)
        page.window.height = assistant.settings.get("window", {}).get("height", 640)

        bridge = FletBridge(page, assistant)

        # ---------------------------------------------------------
        # Avatar (static — see module docstring on scope)
        # ---------------------------------------------------------
        avatar = ft.Container(
            width=64, height=64, border_radius=64,
            bgcolor=theme.ACCENT_DIM,
            border=ft.Border.all(2, theme.ACCENT),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=theme.ACCENT),
        )
        header = ft.Row(
            controls=[avatar, ft.Text("LYRA", size=20, color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD)],
            spacing=12,
        )

        # ---------------------------------------------------------
        # Transcript (console-styled, reuses FletBridge's chat_list
        # contract — bridge.py's chat bubbles still apply; a fully
        # console-styled transcript would replace _chat_bubble() with a
        # Lyra-specific builder the same way Nova could, left as a next
        # step rather than done here)
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
        # Command bar
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
            # Simple slash-command convention for direct agent invocation,
            # e.g. "/weather" — anything else goes to process_message()
            # the same way Nova's tool tray calls agents via buttons
            # instead of typed commands. Two different UX philosophies
            # for the same underlying capability.
            if text.startswith("/"):
                agent_id = AGENT_COMMANDS.get(text[1:].strip().lower())
                if agent_id:
                    bridge.select_agent(agent_id)
                    bridge.run_selected_agent()
                    return
            bridge.send_message(text)

        mic_button = ft.IconButton(
            icon=ft.Icons.MIC_OUTLINED,
            icon_color=theme.ACCENT,
            selected_icon=ft.Icons.MIC,
            selected_icon_color=theme.DANGER,
            on_click=lambda e: bridge.toggle_mic(),
            tooltip="Toggle microphone",
        )

        command_bar = theme.console_panel(
            ft.Row(controls=[mic_button, command_field]),
        )

        # ---------------------------------------------------------
        # Wire it together
        # ---------------------------------------------------------
        bridge.attach(
            chat_list=chat_list,
            typing_indicator=typing_indicator,
            mic_button=mic_button,
            # No waveform/on_state_changed_ui wired for Lyra in this pass
            # — see module docstring.
        )

        page.add(
            ft.Column(
                controls=[header, ft.Container(height=12), transcript, command_bar],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            )
        )

    return main
