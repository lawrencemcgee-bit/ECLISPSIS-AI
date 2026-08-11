"""
Nova's settings panel — voice selection and speech rate.

Scoped deliberately to what's actually real and configurable right now:
VoiceService exposes list_voices()/set_voice()/set_speech_rate(), all
confirmed working end-to-end in live testing. Not a general "app
settings" catch-all — extending this to cover other preferences (theme,
window behavior, etc.) is a separate, later addition, not assumed here.

The actual dialog-building logic now lives in shared_dialogs.py (Lyra
parity work — Lyra needed the identical dialog with its own theme
colors). This file is now just Nova's theme colors passed into the
shared builder — same behavior as before.
"""

import flet as ft

from src.ui_flet.personas.nova import theme
from src.ui_flet.shared_dialogs import build_settings_button as _build


def build_settings_button(page: ft.Page, assistant) -> ft.IconButton:
    return _build(page, assistant, accent=theme.ACCENT, muted=theme.TEXT_MUTED)
