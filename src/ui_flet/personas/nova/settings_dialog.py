"""
Nova's settings panel — voice selection and speech rate.

Scoped deliberately to what's actually real and configurable right now:
VoiceService exposes list_voices()/set_voice()/set_speech_rate(), all
confirmed working end-to-end in live testing. Not a general "app
settings" catch-all — extending this to cover other preferences (theme,
window behavior, etc.) is a separate, later addition, not assumed here.

Same composition pattern as permissions_dialog.py: an IconButton that
opens an ft.AlertDialog, built with controls already proven to work in
this codebase (TextButton, IconButton) rather than introducing a Dropdown
or other control whose exact API surface (e.g. whether its option class
is capitalized or not — a real, repeated surprise elsewhere in this
build) wasn't independently verified.
"""

import flet as ft

from src.ui_flet.personas.nova import theme


def build_settings_button(page: ft.Page, assistant) -> ft.IconButton:
    selected_voice_id = {"value": None}  # mutable box; closures below read/write it

    voice_status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    rate_label = ft.Text("Speech rate: 150 wpm", size=12, color=theme.TEXT_MUTED)

    def refresh_voice_status():
        voices = assistant.list_voices()
        if not voices:
            voice_status.value = "No TTS voices available (pyttsx3 not initialized)."
        else:
            current = selected_voice_id["value"]
            name = next((v["name"] for v in voices if v["id"] == current), None)
            voice_status.value = f"Current: {name}" if name else "No voice selected yet — using system default."
        voice_status.update()

    def build_voice_list():
        voices = assistant.list_voices()
        rows = []
        for v in voices:
            def make_select(voice_id=v["id"]):
                def _select(e):
                    selected_voice_id["value"] = voice_id
                    assistant.set_voice(voice_id)
                    refresh_voice_status()
                return _select

            rows.append(
                ft.TextButton(v["name"], on_click=make_select())
            )
        if not rows:
            rows = [ft.Text("No voices found on this system.", size=12, color=theme.TEXT_MUTED)]
        return ft.Column(controls=rows, spacing=2, tight=True)

    def on_rate_change(e):
        rate = int(e.control.value)
        assistant.set_speech_rate(rate)
        rate_label.value = f"Speech rate: {rate} wpm"
        rate_label.update()

    def test_voice(e):
        assistant.speak("This is a test of the current voice and speech rate.")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Voice Settings"),
        content=ft.Column(
            controls=[
                ft.Text("Voice", weight=ft.FontWeight.BOLD),
                voice_status,
                build_voice_list(),
                ft.Divider(),
                rate_label,
                ft.Slider(min=80, max=250, value=150, divisions=17, on_change=on_rate_change),
                ft.TextButton("Test voice", on_click=test_voice),
            ],
            tight=True,
            spacing=8,
        ),
        actions=[ft.TextButton("Close", on_click=lambda e: close_dialog())],
    )

    def open_dialog(e):
        refresh_voice_status()
        page.show_dialog(dialog)

    def close_dialog():
        dialog.open = False
        page.update()

    return ft.IconButton(
        icon=ft.Icons.TUNE_OUTLINED,
        icon_color=theme.ACCENT,
        tooltip="Voice Settings",
        on_click=open_dialog,
    )
