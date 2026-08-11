"""
Lyra's settings panel — same voice-selection/speech-rate dialog Nova has,
Lyra's amber theme colors. See src/ui_flet/shared_dialogs.py for the
actual logic. Voice settings matter at least as much for Lyra as Nova —
arguably more, given Lyra is the voice-first persona — so this isn't a
scope cut, it's parity.
"""

import flet as ft

from src.ui_flet.personas.lyra import theme
from src.ui_flet.shared_dialogs import build_settings_button as _build


def build_settings_button(page: ft.Page, assistant) -> ft.IconButton:
    return _build(page, assistant, accent=theme.ACCENT, muted=theme.TEXT_MUTED)
