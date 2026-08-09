"""
Nova's permissions panel — lets the user grant/deny microphone and camera
access proactively, ahead of actually trying to use them.

Why proactive rather than a blocking "Allow?" popup at the exact moment
capture is requested: PermissionService.request() (Phase 10) calls its
decision handler synchronously and expects an immediate bool back.
Showing a Flet dialog and waiting for the user's click is inherently
asynchronous — the click is a future callback, not something available
the instant request() runs. Flet runs on a single asyncio event loop;
blocking that same thread to wait for a dialog's own button click would
deadlock, since the click event itself would never get processed while
the loop is stuck waiting on it.

This sidesteps that entirely: granting ahead of time
(assistant.grant_permission()) is a plain synchronous call — it just
persists a decision, nothing to wait for. By the time toggle_mic()/
capture_vision() actually run, PermissionService.request() finds an
already-granted permission and never needs to consult a decision handler
at all.

Confidence note: page.show_dialog(dialog) to open is confirmed correct
(page.open() was confirmed NOT to exist on this Page — see bridge.py's
_toast() history). Closing via dialog.open = False + page.update() is
the long-standing pattern for the control's own property and wasn't
separately verified against this exact Flet version — flagging as the
next most likely thing to need a fix if "Close" doesn't visually work.
"""

import flet as ft

from src.ui_flet.personas.nova import theme

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


def build_permissions_button(page: ft.Page, assistant) -> ft.IconButton:
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
        status_text = ft.Text(_status_of(assistant, permission_id), size=12, color=theme.TEXT_MUTED)
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
                ft.Text(description, size=11, color=theme.TEXT_MUTED),
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
        icon_color=theme.ACCENT,
        tooltip="Permissions",
        on_click=open_dialog,
    )
