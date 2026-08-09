"""
Nova (Approach 1) — Jarvis-style main screen.

create_nova_app(assistant) returns a function suitable for ft.app(target=...).
This is the ONLY place persona-specific layout decisions live; everything
it calls into (FletBridge, AssistantCore) is persona-agnostic. Building
Lyra (Approach 2) means writing a sibling file like this one, not touching
this one or bridge.py.

Confidence: MEDIUM overall — reviewed carefully against Flet ~0.86 docs,
never executed. See bridge.py, orb.py, and waveform.py docstrings for
specific version-sensitivity notes.
"""

import flet as ft

from src.ui_flet.bridge import FletBridge
from src.ui_flet.personas.nova import theme
from src.ui_flet.personas.nova.orb import build_orb
from src.ui_flet.personas.nova.waveform import build_waveform
from src.ui_flet.personas.nova.permissions_dialog import build_permissions_button

AGENTS = [
    ("onenote", ft.Icons.NOTE_ALT_OUTLINED, "Notes"),
    ("weather", ft.Icons.WB_SUNNY_OUTLINED, "Weather"),
    ("news", ft.Icons.NEWSPAPER_OUTLINED, "News"),
]


def create_nova_app(assistant):
    def main(page: ft.Page):
        page.title = "NOVA — ECLIPSIS-AI"
        page.bgcolor = theme.BACKGROUND
        page.theme = theme.page_theme()
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        page.window.width = assistant.settings.get("window", {}).get("width", 1100)
        page.window.height = assistant.settings.get("window", {}).get("height", 720)

        bridge = FletBridge(page, assistant)

        # ---------------------------------------------------------
        # Header (app label + permissions access)
        # ---------------------------------------------------------
        header = ft.Row(
            controls=[
                ft.Text("NOVA", size=14, color=theme.TEXT_MUTED, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                build_permissions_button(page, assistant),
            ],
        )

        # ---------------------------------------------------------
        # Orb + waveform (center focal point)
        # ---------------------------------------------------------
        orb = build_orb(page)
        waveform = build_waveform()

        orb_column = ft.Column(
            controls=[orb, waveform],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
        )

        # ---------------------------------------------------------
        # Agent tool tray
        # ---------------------------------------------------------
        def make_agent_button(agent_id, icon, label):
            def on_click(e):
                bridge.select_agent(agent_id)
                bridge.run_selected_agent()
            return ft.Column(
                controls=[
                    ft.IconButton(icon=icon, icon_color=theme.ACCENT, on_click=on_click, tooltip=label),
                    ft.Text(label, size=11, color=theme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            )

        tool_tray = theme.glass_panel(
            ft.Row(
                controls=[make_agent_button(*a) for a in AGENTS],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
            padding=12,
        )

        # ---------------------------------------------------------
        # Chat panel
        # ---------------------------------------------------------
        chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        typing_indicator = ft.Text("Nova is thinking…", color=theme.TEXT_MUTED, italic=True, visible=False)

        chat_panel = theme.glass_panel(
            ft.Column(
                controls=[
                    ft.Container(content=chat_list, expand=True),
                    typing_indicator,
                ],
                expand=True,
            ),
            expand=True,
        )

        # ---------------------------------------------------------
        # Input bar
        # ---------------------------------------------------------
        message_field = ft.TextField(
            hint_text="Ask Nova anything…",
            expand=True,
            border_color=theme.PANEL_BORDER,
            color=theme.TEXT_PRIMARY,
            on_submit=lambda e: _send(),
        )

        def _send():
            text = message_field.value
            message_field.value = ""
            message_field.update()
            bridge.send_message(text)

        mic_button = ft.IconButton(
            icon=ft.Icons.MIC_OUTLINED,
            icon_color=theme.ACCENT,
            selected_icon=ft.Icons.MIC,
            selected_icon_color=theme.DANGER,
            on_click=lambda e: (bridge.toggle_mic(), orb.set_state("listening" if assistant.audio.active else "idle")),
            tooltip="Toggle microphone",
        )

        camera_button = ft.IconButton(
            icon=ft.Icons.CAMERA_ALT_OUTLINED,
            icon_color=theme.ACCENT,
            on_click=lambda e: bridge.capture_vision(),
            tooltip="Capture vision snapshot",
        )

        input_bar = theme.glass_panel(
            ft.Row(controls=[
                mic_button,
                camera_button,
                message_field,
                ft.IconButton(icon=ft.Icons.SEND_OUTLINED, icon_color=theme.ACCENT, on_click=lambda e: _send()),
            ]),
            padding=8,
        )

        # ---------------------------------------------------------
        # Wire it all together
        # ---------------------------------------------------------
        bridge.attach(
            chat_list=chat_list,
            typing_indicator=typing_indicator,
            waveform=waveform,
            mic_button=mic_button,
            on_state_changed_ui=orb.set_state,
        )
        orb.start_pulse()

        def on_window_event(e: ft.WindowEvent):
            if e.type in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED):
                bridge.save_window_geometry()
        page.window.on_event = on_window_event  # confirmed against current Window docs

        page.add(
            ft.Column(
                controls=[
                    ft.Container(content=header, padding=16),
                    orb_column,
                    ft.Container(height=12),
                    tool_tray,
                    ft.Container(height=12),
                    chat_panel,
                    input_bar,
                    ft.Container(height=12),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            )
        )

        bridge.scroll_chat_to_end_now()

    return main
