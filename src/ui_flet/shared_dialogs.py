"""
Persona-agnostic settings/permissions dialog builders.

Extracted during Lyra-parity work from what was originally
nova/settings_dialog.py and nova/permissions_dialog.py, verbatim in logic
— only the hardcoded `from src.ui_flet.personas.nova import theme` import
changed to two explicit color parameters (accent, muted), since that was
the only persona-specific thing either file actually used. Nova's two
files now just call these with its own theme colors; Lyra's do the same
with its own. No behavior change for Nova.
"""

import flet as ft

PERMISSIONS = [
    ("access_microphone", "Microphone", "Needed for voice input (speech-to-text)."),
    ("access_camera", "Camera", "Needed for vision snapshots."),
]


def _status_of(assistant, permission_id):
    if permission_id in assistant.permissions.granted:
        return "Granted"
    if permission_id in assistant.permissions.denied:
        return "Denied"
    return "Not decided"


def build_permissions_button(page: ft.Page, assistant, accent: str, muted: str) -> ft.IconButton:
    """Returns an IconButton that opens the permissions dialog when
    clicked. Composition, not a custom Control subclass — same reasoning
    as orb.py/waveform.py: no dependency on whichever custom-component
    pattern Flet settles on for 1.0."""

    status_texts = {}

    def refresh_statuses():
        for permission_id, text_control in status_texts.items():
            text_control.value = _status_of(assistant, permission_id)
            text_control.update()

    def make_row(permission_id, label, description):
        status_text = ft.Text(_status_of(assistant, permission_id), size=12, color=muted)
        status_texts[permission_id] = status_text

        def grant(e):
            assistant.grant_permission(permission_id)
            refresh_statuses()

        def deny(e):
            assistant.deny_permission(permission_id)
            refresh_statuses()

        def reset(e):
            assistant.revoke_permission(permission_id)
            refresh_statuses()

        return ft.Column(
            controls=[
                ft.Row(controls=[
                    ft.Text(label, weight=ft.FontWeight.BOLD, expand=True),
                    status_text,
                ]),
                ft.Text(description, size=11, color=muted),
                ft.Row(controls=[
                    ft.TextButton("Allow", on_click=grant),
                    ft.TextButton("Deny", on_click=deny),
                    ft.TextButton("Reset", on_click=reset),
                ]),
            ],
            spacing=4,
        )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Permissions"),
        content=ft.Column(
            controls=[make_row(pid, label, desc) for pid, label, desc in PERMISSIONS],
            tight=True,
            spacing=16,
        ),
        actions=[ft.TextButton("Close", on_click=lambda e: close_dialog())],
    )

    def open_dialog(e):
        refresh_statuses()
        page.show_dialog(dialog)

    def close_dialog():
        dialog.open = False
        page.update()

    return ft.IconButton(
        icon=ft.Icons.SECURITY_OUTLINED,
        icon_color=accent,
        tooltip="Permissions",
        on_click=open_dialog,
    )


def build_settings_button(page: ft.Page, assistant, accent: str, muted: str) -> ft.IconButton:
    """Voice settings — voice selection and speech rate. Scoped to what's
    actually real and configurable right now: VoiceService exposes
    list_voices()/set_voice()/set_speech_rate(), all confirmed working
    end-to-end in live testing. Not a general "app settings" catch-all."""

    selected_voice_id = {"value": None}  # mutable box; closures below read/write it

    voice_status = ft.Text("", size=12, color=muted)
    rate_label = ft.Text("Speech rate: 150 wpm", size=12, color=muted)

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
            rows = [ft.Text("No voices found on this system.", size=12, color=muted)]
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
        icon_color=accent,
        tooltip="Voice Settings",
        on_click=open_dialog,
    )
