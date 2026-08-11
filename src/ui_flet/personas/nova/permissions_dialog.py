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

The actual dialog-building logic now lives in shared_dialogs.py (Lyra
parity work — Lyra needed the identical dialog with its own theme
colors, and duplicating ~90 lines to change one import wasn't worth it).
This file is now just Nova's theme colors passed into the shared
builder — same behavior as before.
"""

import flet as ft

from src.ui_flet.personas.nova import theme
from src.ui_flet.shared_dialogs import build_permissions_button as _build


def build_permissions_button(page: ft.Page, assistant) -> ft.IconButton:
    return _build(page, assistant, accent=theme.ACCENT, muted=theme.TEXT_MUTED)
